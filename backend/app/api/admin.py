import base64
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, func, or_, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, hash_password
from app.database.deps import get_db
from app.models.package import Package
from app.models.session import Session as UserSession
from app.models.user import User
from app.models.workflow import Workflow
from app.models.workflow_execution import (
    ExecutionStatus,
    NodeExecutionLog,
    WorkflowExecution,
)

# Temporarily disabled because these modules are not available
# from app.services.engine.cancel import cancel_execution
# from app.services.package_runner import (
#     ALLOWED_EXT,
#     MAX_PACKAGE_BYTES,
#     PKG_DIR,
#     SERVER_PLATFORM,
# )


MAX_ICON_BYTES = 200 * 1024

TABLES_WITH_USER_ID = (
    "awf_llm_connections",
    "awf_scheduled_workflows",
    "awf_app_integrations",
)


# ═══════════════════════════ Admin Authorization ═══════════════════════════

async def require_admin(
    user: User = Depends(get_current_user),
) -> User:
    if user.role != "admin":
        raise HTTPException(403, "Admin access required")

    return user


router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(require_admin)],
)

public_router = APIRouter(tags=["Packages"])


# ═══════════════════════════ Helpers ═══════════════════════════

def _uuid(value: str, what: str = "id") -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except ValueError:
        raise HTTPException(400, f"Invalid {what}")


def _iso(d):
    return d.isoformat() if d else None


# ═══════════════════════════ /me and /packages ═══════════════════════════
# These endpoints are available to logged-in users.
#
# NOTE:
# The package listing is kept because it only reads the Package table.
# Package upload/runtime management is disabled below.


@public_router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "role": user.role,
    }


def _pkg_out(p: Package, admin: bool = False) -> dict:
    out = {
        "id": str(p.id),
        "node_type": f"pkg_{p.id.hex}",
        "name": p.name,
        "description": p.description,
        "kind": p.kind,
        "icon": p.icon,
    }

    if admin:
        out |= {
            "platform": p.platform,
            "size": p.size,
            "sha256": p.sha256,
            "original_name": p.original_name,
            "is_active": p.is_active,
            "created_at": _iso(p.created_at),
        }

    return out


@public_router.get("/packages")
async def list_active_packages(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = await db.scalars(
        select(Package)
        .where(Package.is_active.is_(True))
        .order_by(Package.name)
    )

    return [_pkg_out(p) for p in rows]


# ═══════════════════════════ Stats ═══════════════════════════

@router.get("/stats")
async def stats(
    db: AsyncSession = Depends(get_db),
):
    since = datetime.now(timezone.utc) - timedelta(hours=24)

    async def count(model, *where):
        return (
            await db.execute(
                select(func.count())
                .select_from(model)
                .where(*where)
            )
        ).scalar() or 0

    return {
        "users": await count(User),

        "active_users": await count(
            User,
            User.is_active.is_(True),
        ),

        "admins": await count(
            User,
            User.role == "admin",
        ),

        "workflows": await count(Workflow),

        "running_now": await count(
            WorkflowExecution,
            WorkflowExecution.status == ExecutionStatus.RUNNING,
        ),

        "runs_24h": await count(
            WorkflowExecution,
            WorkflowExecution.created_at >= since,
        ),

        "failed_24h": await count(
            WorkflowExecution,
            WorkflowExecution.created_at >= since,
            WorkflowExecution.status.in_(
                [
                    ExecutionStatus.FAILED,
                    ExecutionStatus.PARTIAL,
                ]
            ),
        ),

        "packages": await count(Package),
    }


# ═══════════════════════════ Users ═══════════════════════════

class UserCreate(BaseModel):
    username: str = Field(
        min_length=3,
        max_length=50,
    )

    email: EmailStr

    password: str = Field(
        min_length=6,
        max_length=128,
    )

    role: str = "user"


class UserUpdate(BaseModel):
    username: Optional[str] = Field(
        None,
        min_length=3,
        max_length=50,
    )

    email: Optional[EmailStr] = None

    password: Optional[str] = Field(
        None,
        min_length=6,
        max_length=128,
    )

    is_active: Optional[bool] = None
    role: Optional[str] = None


async def _users_payload(
    db: AsyncSession,
    users: list[User],
) -> list[dict]:

    async def by_user(q):
        return {
            str(k): v
            for k, v in (await db.execute(q)).all()
        }

    wf = await by_user(
        select(
            Workflow.user_id,
            func.count(),
        ).group_by(
            Workflow.user_id
        )
    )

    runs = await by_user(
        select(
            WorkflowExecution.user_id,
            func.count(),
        ).group_by(
            WorkflowExecution.user_id
        )
    )

    last = await by_user(
        select(
            WorkflowExecution.user_id,
            func.max(WorkflowExecution.created_at),
        ).group_by(
            WorkflowExecution.user_id
        )
    )

    return [
        {
            "id": str(u.id),
            "username": u.username,
            "email": u.email,
            "is_active": u.is_active,
            "role": u.role,
            "created_at": _iso(u.created_at),
            "workflows": wf.get(str(u.id), 0),
            "runs": runs.get(str(u.id), 0),
            "last_run_at": _iso(
                last.get(str(u.id))
            ),
        }
        for u in users
    ]


async def _get_user(
    db: AsyncSession,
    user_id: str,
) -> User:

    u = await db.get(
        User,
        _uuid(user_id, "user id"),
    )

    if not u:
        raise HTTPException(
            404,
            "User not found",
        )

    return u


async def _email_taken(
    db: AsyncSession,
    email: str,
    exclude: Optional[uuid.UUID] = None,
) -> bool:

    q = (
        select(func.count())
        .select_from(User)
        .where(
            func.lower(User.email) == email.lower()
        )
    )

    if exclude:
        q = q.where(User.id != exclude)

    return (
        await db.execute(q)
    ).scalar() > 0


async def _other_active_admins(
    db: AsyncSession,
    exclude: uuid.UUID,
) -> bool:

    q = (
        select(func.count())
        .select_from(User)
        .where(
            User.role == "admin",
            User.is_active.is_(True),
            User.id != exclude,
        )
    )

    return (
        await db.execute(q)
    ).scalar() > 0


@router.get("/users")
async def list_users(
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):

    q = select(User).order_by(
        User.created_at.desc()
    )

    if search:
        like = f"%{search.lower()}%"

        q = q.where(
            or_(
                func.lower(User.email).like(like),
                func.lower(User.username).like(like),
            )
        )

    return await _users_payload(
        db,
        list(await db.scalars(q)),
    )


@router.post("/users", status_code=201)
async def create_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
):

    if await _email_taken(
        db,
        body.email,
    ):
        raise HTTPException(
            409,
            "A user with that email already exists",
        )

    u = User(
        username=body.username.strip(),
        email=body.email.strip(),
        password=hash_password(body.password),
        is_verified=True,
        role=body.role,
    )

    db.add(u)

    await db.flush()

    return (
        await _users_payload(
            db,
            [u],
        )
    )[0]


@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):

    u = await _get_user(
        db,
        user_id,
    )

    if (
        u.id == admin.id
        and (
            body.is_active is False
            or body.role == "user"
        )
    ):
        raise HTTPException(
            400,
            "You can't deactivate or demote your own account",
        )

    if (
        u.role
        and (
            body.role == "user"
            or body.is_active is False
        )
        and not await _other_active_admins(
            db,
            u.id,
        )
    ):
        raise HTTPException(
            400,
            "At least one active admin is required",
        )

    if (
        body.email
        and body.email.lower() != u.email.lower()
    ):

        if await _email_taken(
            db,
            body.email,
            u.id,
        ):
            raise HTTPException(
                409,
                "A user with that email already exists",
            )

        u.email = body.email.strip()

    if body.username:
        u.username = body.username.strip()

    if body.password:
        u.password = hash_password(
            body.password
        )

    if body.is_active is not None:
        u.is_active = body.is_active

    if body.role is not None:
        u.role = body.role

    if body.is_active is False:
        await db.execute(
            update(UserSession)
            .where(
                UserSession.user_id == u.id
            )
            .values(
                is_active=False
            )
        )

    await db.flush()

    return (
        await _users_payload(
            db,
            [u],
        )
    )[0]


@router.delete(
    "/users/{user_id}",
    status_code=204,
)
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):

    u = await _get_user(
        db,
        user_id,
    )

    if u.id == admin.id:
        raise HTTPException(
            400,
            "You can't delete your own account",
        )

    if (
        u.role
        and not await _other_active_admins(
            db,
            u.id,
        )
    ):
        raise HTTPException(
            400,
            "At least one active admin is required",
        )

    for table in TABLES_WITH_USER_ID:
        try:
            async with db.begin_nested():
                await db.execute(
                    text(
                        f"DELETE FROM {table} "
                        "WHERE user_id::text = :u"
                    ),
                    {
                        "u": str(u.id)
                    },
                )
        except Exception:
            pass

    # Workflows, executions, node logs and sessions
    # go with the user (ON DELETE CASCADE)

    await db.execute(
        delete(User).where(
            User.id == u.id
        )
    )


# ═══════════════════════════ Run History ═══════════════════════════

def _node_out(
    n: NodeExecutionLog,
    include_data: bool,
) -> dict:

    out = {
        "node_id": n.node_id,
        "node_type": n.node_type,
        "node_label": n.node_label,
        "sequence": n.sequence,
        "status": (
            n.status.value
            if hasattr(n.status, "value")
            else str(n.status)
        ),
        "log_message": n.log_message,
        "error_message": n.error_message,
        "duration_ms": n.duration_ms,
        "branch_taken": n.branch_taken,
    }

    if include_data:
        out |= {
            "input_context": n.input_context,
            "output_context": n.output_context,
            "context_diff": n.context_diff,
        }

    return out


@router.get("/runs")
async def list_runs(
    user_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 25,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):

    where = []

    if user_id:
        where.append(
            WorkflowExecution.user_id
            == _uuid(user_id, "user id")
        )

    if status:
        try:
            where.append(
                WorkflowExecution.status
                == ExecutionStatus(status)
            )
        except ValueError:
            raise HTTPException(
                400,
                "Invalid status",
            )

    total = (
        await db.execute(
            select(func.count())
            .select_from(WorkflowExecution)
            .where(*where)
        )
    ).scalar() or 0

    rows = list(
        await db.scalars(
            select(WorkflowExecution)
            .where(*where)
            .order_by(
                WorkflowExecution.created_at.desc()
            )
            .limit(
                min(
                    max(limit, 1),
                    200,
                )
            )
            .offset(
                max(offset, 0)
            )
        )
    )

    users = (
        {
            str(u.id): u
            for u in await db.scalars(
                select(User).where(
                    User.id.in_(
                        {
                            r.user_id
                            for r in rows
                        }
                    )
                )
            )
        }
        if rows
        else {}
    )

    wf_ids = set()

    for r in rows:
        try:
            wf_ids.add(
                uuid.UUID(
                    str(r.workflow_id)
                )
            )
        except ValueError:
            pass

    wfs = (
        {
            str(w.id): w.name
            for w in await db.scalars(
                select(Workflow).where(
                    Workflow.id.in_(wf_ids)
                )
            )
        }
        if wf_ids
        else {}
    )

    data = [
        {
            "id": str(r.id),
            "status": (
                r.status.value
                if hasattr(r.status, "value")
                else str(r.status)
            ),
            "workflow_id": str(r.workflow_id),
            "workflow_name": wfs.get(
                str(r.workflow_id),
                "(deleted)",
            ),
            "user_id": str(r.user_id),
            "username": getattr(
                users.get(str(r.user_id)),
                "username",
                "?",
            ),
            "email": getattr(
                users.get(str(r.user_id)),
                "email",
                "?",
            ),
            "created_at": _iso(
                r.created_at
            ),
            "completed_at": _iso(
                r.completed_at
            ),
            "duration_ms": r.duration_ms,
            "nodes_total": r.nodes_total,
            "nodes_success": r.nodes_success,
            "nodes_failed": r.nodes_failed,
            "error_message": r.error_message,
        }
        for r in rows
    ]

    return {
        "data": data,
        "total": total,
    }


@router.get(
    "/runs/{execution_id}/nodes"
)
async def run_nodes(
    execution_id: str,
    include_data: bool = False,
    db: AsyncSession = Depends(get_db),
):

    eid = _uuid(
        execution_id,
        "execution id",
    )

    logs = await db.scalars(
        select(NodeExecutionLog)
        .where(
            NodeExecutionLog.execution_id == eid
        )
        .order_by(
            NodeExecutionLog.sequence
        )
    )

    return {
        "data": [
            _node_out(
                n,
                include_data,
            )
            for n in logs
        ]
    }


# ═══════════════════════════════════════════════════════════════════════
# TERMINATE RUN - TEMPORARILY DISABLED
#
# The cancel service does not currently exist:
#
# from app.services.engine.cancel import cancel_execution
#
# Keep this endpoint commented until the execution cancellation service
# is implemented.
# ═══════════════════════════════════════════════════════════════════════

# @router.post("/runs/{execution_id}/terminate")
# async def terminate_run(
#     execution_id: str,
#     db: AsyncSession = Depends(get_db),
# ):
#     ex = await db.get(
#         WorkflowExecution,
#         _uuid(execution_id, "execution id"),
#     )
#
#     if not ex:
#         raise HTTPException(
#             404,
#             "Execution not found",
#         )
#
#     if ex.status != ExecutionStatus.RUNNING:
#         raise HTTPException(
#             400,
#             "Execution is not running",
#         )
#
#     if cancel_execution(str(ex.id)):
#         return {
#             "message": "Stop signal sent"
#         }
#
#     ex.status = ExecutionStatus.CANCELLED
#     ex.completed_at = datetime.now(timezone.utc)
#
#     return {
#         "message": "Run was no longer active; marked as cancelled"
#     }


# ═══════════════════════════════════════════════════════════════════════
# PACKAGE MANAGEMENT - TEMPORARILY DISABLED
#
# These endpoints require:
#
# app.services.package_runner
#
# which is currently unavailable.
#
# Package listing for active packages remains available above through
# /packages.
#
# The admin package upload/update/delete/runtime functionality is
# commented out until package_runner is implemented.
# ═══════════════════════════════════════════════════════════════════════


# async def _save_package_file(file: UploadFile) -> dict:
#     ext = Path(file.filename or "").suffix.lower()
#
#     if ext not in ALLOWED_EXT:
#         raise HTTPException(
#             400,
#             f"Unsupported file type. Allowed: "
#             f"{', '.join(sorted(ALLOWED_EXT))}",
#         )
#
#     PKG_DIR.mkdir(
#         parents=True,
#         exist_ok=True,
#     )
#
#     stored = f"{uuid.uuid4().hex}{ext}"
#
#     dest = PKG_DIR / stored
#     h = hashlib.sha256()
#     size = 0
#     head = b""
#
#     try:
#         with open(dest, "wb") as out:
#             while chunk := await file.read(1 << 20):
#                 head = head or chunk[:4]
#                 size += len(chunk)
#
#                 if size > MAX_PACKAGE_BYTES:
#                     raise HTTPException(
#                         413,
#                         f"File is larger than "
#                         f"{MAX_PACKAGE_BYTES // (1024 * 1024)} MB",
#                     )
#
#                 h.update(chunk)
#                 out.write(chunk)
#
#         platform = (
#             "windows"
#             if head[:2] == b"MZ"
#             else "linux"
#             if head == b"\x7fELF"
#             else None
#         )
#
#         if platform is None:
#             raise HTTPException(
#                 400,
#                 "Not a valid Windows (PE) or Linux (ELF) binary",
#             )
#
#         if platform != SERVER_PLATFORM:
#             raise HTTPException(
#                 400,
#                 f"This is a {platform} binary but the server runs "
#                 f"{SERVER_PLATFORM}. Upload a {SERVER_PLATFORM} build, "
#                 f"or run the backend on {platform}.",
#             )
#
#     except BaseException:
#         dest.unlink(
#             missing_ok=True
#         )
#         raise
#
#     if SERVER_PLATFORM == "linux":
#         dest.chmod(0o700)
#
#     return {
#         "kind": ALLOWED_EXT[ext],
#         "platform": platform,
#         "original_name": Path(file.filename).name[:255],
#         "stored_name": stored,
#         "sha256": h.hexdigest(),
#         "size": size,
#     }


# async def _read_icon(
#     icon: Optional[UploadFile],
# ) -> Optional[str]:
#
#     if icon is None or not icon.filename:
#         return None
#
#     raw = await icon.read(
#         MAX_ICON_BYTES + 1
#     )
#
#     if len(raw) > MAX_ICON_BYTES:
#         raise HTTPException(
#             400,
#             "Icon must be 200 KB or smaller",
#         )
#
#     mime = (
#         "image/png"
#         if raw.startswith(
#             b"\x89PNG\r\n\x1a\n"
#         )
#         else "image/jpeg"
#         if raw.startswith(
#             b"\xff\xd8\xff"
#         )
#         else "image/webp"
#         if raw[:4] == b"RIFF"
#         and raw[8:12] == b"WEBP"
#         else None
#     )
#
#     if not mime:
#         raise HTTPException(
#             400,
#             "Icon must be a PNG, JPEG or WebP image",
#         )
#
#     return (
#         f"data:{mime};base64,"
#         f"{base64.b64encode(raw).decode()}"
#     )


# def _clean_name(name: str) -> str:
#     name = (name or "").strip()
#
#     if not 2 <= len(name) <= 60:
#         raise HTTPException(
#             400,
#             "Name must be 2-60 characters",
#         )
#
#     return name


# @router.get("/packages/runtime")
# async def package_runtime():
#     return {
#         "platform": SERVER_PLATFORM,
#         "extensions": sorted(ALLOWED_EXT),
#         "max_mb": MAX_PACKAGE_BYTES // (1024 * 1024),
#     }


# @router.get("/packages")
# async def admin_list_packages(
#     db: AsyncSession = Depends(get_db),
# ):
#     return [
#         _pkg_out(
#             p,
#             admin=True,
#         )
#         for p in await db.scalars(
#             select(Package)
#             .order_by(
#                 Package.created_at.desc()
#             )
#         )
#     ]


# @router.post(
#     "/packages",
#     status_code=201,
# )
# async def create_package(
#     name: str = Form(...),
#     description: str = Form(""),
#     file: UploadFile = File(...),
#     icon: Optional[UploadFile] = File(None),
#     db: AsyncSession = Depends(get_db),
#     admin: User = Depends(require_admin),
# ):
#
#     name = _clean_name(name)
#     icon_url = await _read_icon(icon)
#     meta = await _save_package_file(file)
#
#     p = Package(
#         name=name,
#         description=description.strip()[:1000],
#         icon=icon_url,
#         created_by=str(admin.id),
#         **meta,
#     )
#
#     db.add(p)
#
#     try:
#         await db.flush()
#     except IntegrityError:
#         (
#             PKG_DIR / meta["stored_name"]
#         ).unlink(
#             missing_ok=True
#         )
#
#         raise HTTPException(
#             409,
#             "A package with that name already exists",
#         )
#
#     return _pkg_out(
#         p,
#         admin=True,
#     )


# @router.put(
#     "/packages/{package_id}"
# )
# async def update_package(
#     package_id: str,
#     name: Optional[str] = Form(None),
#     description: Optional[str] = Form(None),
#     is_active: Optional[bool] = Form(None),
#     file: Optional[UploadFile] = File(None),
#     icon: Optional[UploadFile] = File(None),
#     db: AsyncSession = Depends(get_db),
# ):
#
#     p = await db.get(
#         Package,
#         _uuid(
#             package_id,
#             "package id",
#         ),
#     )
#
#     if not p:
#         raise HTTPException(
#             404,
#             "Package not found",
#         )
#
#     icon_url = await _read_icon(icon)
#     old_file = None
#
#     if file is not None and file.filename:
#         meta = await _save_package_file(file)
#         old_file = p.stored_name
#
#         for k, v in meta.items():
#             setattr(
#                 p,
#                 k,
#                 v,
#             )
#
#     if name is not None:
#         p.name = _clean_name(name)
#
#     if description is not None:
#         p.description = description.strip()[:1000]
#
#     if is_active is not None:
#         p.is_active = is_active
#
#     if icon_url:
#         p.icon = icon_url
#
#     try:
#         await db.flush()
#     except IntegrityError:
#         raise HTTPException(
#             409,
#             "A package with that name already exists",
#         )
#
#     if old_file:
#         (
#             PKG_DIR / old_file
#         ).unlink(
#             missing_ok=True
#         )
#
#     return _pkg_out(
#         p,
#         admin=True,
#     )


# @router.delete(
#     "/packages/{package_id}",
#     status_code=204,
# )
# async def delete_package(
#     package_id: str,
#     db: AsyncSession = Depends(get_db),
# ):
#
#     p = await db.get(
#         Package,
#         _uuid(
#             package_id,
#             "package id",
#         ),
#     )
#
#     if not p:
#         raise HTTPException(
#             404,
#             "Package not found",
#         )
#
#     stored = p.stored_name
#
#     await db.delete(p)
#     await db.flush()
#
#     (
#         PKG_DIR / stored
#     ).unlink(
#         missing_ok=True
#     )