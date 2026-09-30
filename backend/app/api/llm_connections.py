from typing import Optional, Tuple
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import httpx

from app.database.deps import get_db
from app.core.security import get_current_user,encrypt_data,decrypt_data
from app.models.llm_connection import LLMConnection
from app.schemas.llm_connection import * 


router = APIRouter(prefix="/llm-connections", tags=["llm-connections"])

# -------------------------
# TEST CONNECTION
# -------------------------
async def _test_connection(
    provider: str,
    api_key: Optional[str],
    model: str,
    base_url: Optional[str] = None
) -> Tuple[bool, str]:

    try:
        async with httpx.AsyncClient() as client:

            # ---------------- OPENAI ----------------
            if provider == "openai":
                url = (base_url or "https://api.openai.com").rstrip("/")

                resp = await client.post(
                    f"{url}/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": "hi"}],
                        "max_tokens": 10,
                    },
                    timeout=15,
                )

            # ---------------- ANTHROPIC ----------------
            elif provider == "anthropic":
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": model,
                        "max_tokens": 10,
                        "messages": [{"role": "user", "content": "hi"}],
                    },
                    timeout=15,
                )

            # ---------------- GROQ ----------------
            elif provider == "groq":
                resp = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": "hi"}],
                        "max_tokens": 10,
                    },
                    timeout=15,
                )

            # ---------------- OLLAMA (FIXED) ----------------
            elif provider == "ollama":
                url = (base_url or "http://host.docker.internal:11434").rstrip("/")

                # IMPORTANT FIX: use /api/chat (more stable)
                resp = await client.post(
                    f"{url}/api/chat",
                    json={
                        "model": model,
                        "messages": [
                            {"role": "user", "content": "hi"}
                        ],
                        "stream": False,
                    },
                    timeout=20,
                )

            else:
                return False, "Unknown provider"

            # ---------------- SAFE RESPONSE PARSING ----------------
            try:
                data = resp.json()
            except Exception:
                return False, f"Non-JSON response: {resp.text}"

            if resp.status_code != 200:
                return False, f"HTTP {resp.status_code}: {data}"

            if isinstance(data, dict) and data.get("error"):
                return False, str(data["error"])

            return True, "Connection successful"

    except Exception as e:
        return False, str(e)


# -------------------------
# LIST
# -------------------------
@router.get("/")
async def list_connections(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(LLMConnection).where(
            LLMConnection.user_id == str(current_user.id)
        )
    )

    conns = result.scalars().all()

    return [
        {
            "id": c.id,
            "name": c.name,
            "provider": c.provider,
            "model": c.model,
            "base_url": c.base_url,
            "is_default": c.is_default,
            "created_at": c.created_at,
            "has_key": bool(c.api_key),
        }
        for c in conns
    ]


# -------------------------
# TEST ENDPOINT
# -------------------------
@router.post("/test")
async def test_connection(
    payload: LLMConnectionCreate,
    current_user=Depends(get_current_user),
):
    dec_api_key = decrypt_data(payload.api_key)
    ok, msg = await _test_connection(
        payload.provider,
        dec_api_key,
        payload.model,
        payload.base_url,
    )
    return {"success": ok, "message": msg}


# -------------------------
# CREATE
# -------------------------
@router.post("/")
async def create_connection(
    payload: LLMConnectionCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # unset previous default
    if payload.is_default:
        result = await db.execute(
            select(LLMConnection).where(
                LLMConnection.user_id == str(current_user.id),
                LLMConnection.is_default == True,
            )
        )
        for c in result.scalars().all():
            c.is_default = False
    enc_api_key = encrypt_data(payload.api_key)
    conn = LLMConnection(
        user_id=str(current_user.id),
        name=payload.name,
        provider=payload.provider,
        api_key=enc_api_key,
        base_url=payload.base_url,
        model=payload.model,
        is_default=payload.is_default,
    )

    db.add(conn)
    await db.commit()
    await db.refresh(conn)

    return {
        "id": conn.id,
        "name": conn.name,
        "provider": conn.provider,
        "model": conn.model,
        "is_default": conn.is_default,
    }


# -------------------------
# DELETE
# -------------------------
@router.delete("/{connection_id}", status_code=204)
async def delete_connection(
    connection_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(LLMConnection).where(
            LLMConnection.id == connection_id,
            LLMConnection.user_id == str(current_user.id),
        )
    )

    conn = result.scalar_one_or_none()

    if not conn:
        raise HTTPException(404, "Connection not found")

    await db.delete(conn)
    await db.commit()