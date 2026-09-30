from typing import Optional
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt_json, encrypt_json
from app.core.security import get_current_user
from app.database.deps import get_db
from app.models.app_integration import AppIntegration
from app.models.user import User
from app.schemas.app_integration import (
    IntegrationCreate, IntegrationOut, IntegrationTestDraft, IntegrationUpdate, TestResult,
)
from app.schemas.app_integration_catalog import CATALOG
from app.services.integration_tester import run_test

router = APIRouter(prefix="/integrations", tags=["App integrations"])


# ------------------------------------------------------------------ helpers
def _split_config(app: str, config: dict[str, str]) -> tuple[dict, dict]:
    """Split the form payload into (public, secret). Blank secrets are dropped (= keep existing)."""
    spec = CATALOG[app]
    unknown = set(config) - spec.public - spec.secret
    if unknown:
        raise HTTPException(422, f"Unknown field(s) for {app}: {', '.join(sorted(unknown))}")
    public = {k: v.strip() for k, v in config.items() if k in spec.public}
    secret = {k: v.strip() for k, v in config.items() if k in spec.secret and v.strip()}
    return public, secret


def _to_out(row: AppIntegration) -> IntegrationOut:
    return IntegrationOut(
        id=row.id, app=row.app, name=row.name, config=row.config or {},
        configured_secrets=sorted(decrypt_json(row.secrets_encrypted).keys()),
        status=row.status, last_checked=row.last_checked, last_error=row.last_error,
        created_at=row.created_at, updated_at=row.updated_at,
    )


async def _get_owned(db: AsyncSession, user: User, integration_id: uuid.UUID) -> AppIntegration:
    row = await db.scalar(
        select(AppIntegration).where(AppIntegration.id == integration_id, AppIntegration.user_id == user.id)
    )
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Integration not found")
    return row


def _merge_secrets(old_public: dict, old_secret: dict, new_public: dict, new_secret: dict) -> dict:
    """Keep stored secrets unless the auth mode changed (then old secrets no longer apply)."""
    if old_public.get("authMode") != new_public.get("authMode"):
        return new_secret
    return {**old_secret, **new_secret}


# ------------------------------------------------------------------ routes
@router.get("/", response_model=list[IntegrationOut])
async def list_integrations(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    rows = await db.scalars(
        select(AppIntegration).where(AppIntegration.user_id == user.id).order_by(AppIntegration.created_at.desc())
    )
    return [_to_out(r) for r in rows]


@router.post("/", response_model=IntegrationOut, status_code=status.HTTP_201_CREATED)
async def create_integration(
    body: IntegrationCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    public, secret = _split_config(body.app, body.config)
    row = AppIntegration(
        user_id=user.id, app=body.app, name=body.name,
        config=public, secrets_encrypted=encrypt_json(secret),
    )
    db.add(row)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "You already have a connection with that name")
    await db.refresh(row)
    return _to_out(row)


@router.put("/{integration_id}", response_model=IntegrationOut)
async def update_integration(
    integration_id: uuid.UUID, body: IntegrationUpdate,
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user),
):
    row = await _get_owned(db, user, integration_id)
    if body.app and body.app != row.app:
        raise HTTPException(400, "The app type cannot be changed; create a new connection instead")

    if body.name:
        row.name = body.name
    if body.config is not None:
        public, secret = _split_config(row.app, body.config)
        row.secrets_encrypted = encrypt_json(
            _merge_secrets(row.config or {}, decrypt_json(row.secrets_encrypted), public, secret)
        )
        row.config = public
        row.status, row.last_error = "untested", None   # credentials changed -> needs re-test

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "You already have a connection with that name")
    await db.refresh(row)
    return _to_out(row)


@router.delete("/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_integration(
    integration_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    row = await _get_owned(db, user, integration_id)
    await db.delete(row)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/test", response_model=TestResult)
async def test_draft(
    body: IntegrationTestDraft, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    """Test credentials from the form without saving them."""
    public, secret = _split_config(body.app, body.config)
    if body.id:  # editing: fill in blank secrets from the stored copy
        row = await _get_owned(db, user, body.id)
        if row.app != body.app:
            raise HTTPException(400, "App type mismatch")
        secret = _merge_secrets(row.config or {}, decrypt_json(row.secrets_encrypted), public, secret)
    ok, message = await run_test(body.app, {**public, **secret})
    return TestResult(ok=ok, message=message)


@router.post("/{integration_id}/test", response_model=TestResult)
async def test_saved(
    integration_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    row = await _get_owned(db, user, integration_id)
    ok, message = await run_test(row.app, {**(row.config or {}), **decrypt_json(row.secrets_encrypted)})
    row.status = "connected" if ok else "failed"
    row.last_checked = datetime.now(timezone.utc)
    row.last_error = None if ok else message
    await db.commit()
    return TestResult(ok=ok, message=message)

@router.get("/options")
async def list_node_connections(
    app: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(AppIntegration).where(AppIntegration.user_id == user.id, AppIntegration.is_active.is_(True))
    if app:
        q = q.where(AppIntegration.app == app)
    rows = await db.scalars(q.order_by(AppIntegration.created_at))
    return [{"id": str(r.id), "name": r.name, "app": r.app, "status": r.status} for r in rows]