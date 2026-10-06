from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, field_validator


# ── Request schemas ───────────────────────────────────────────────────────────

class ScheduleCreate(BaseModel):
    freq: str = "manual"
    cron: Optional[str] = None
    time: Optional[str] = None
    day: Optional[str] = None
    enabled: bool = True

    @field_validator("freq")
    @classmethod
    def valid_freq(cls, v: str) -> str:
        allowed = {
            "manual",
            "minutely",
            "hourly",
            "daily",
            "weekly",
            "monthly",
            "custom",
        }
        if v not in allowed:
            raise ValueError(f"freq must be one of {allowed}")
        return v

    @field_validator("cron")
    @classmethod
    def cron_required_for_custom(cls, v, info):
        if info.data.get("freq") == "custom" and not v:
            raise ValueError(
                "cron expression is required when freq is 'custom'"
            )
        return v


class ScheduleUpdate(BaseModel):
    freq: Optional[str] = None
    cron: Optional[str] = None
    time: Optional[str] = None
    day: Optional[str] = None
    enabled: Optional[bool] = None

    @field_validator("freq")
    @classmethod
    def valid_freq(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v

        allowed = {
            "manual",
            "minutely",
            "hourly",
            "daily",
            "weekly",
            "monthly",
            "custom",
        }

        if v not in allowed:
            raise ValueError(f"freq must be one of {allowed}")

        return v


# ── Response schemas ──────────────────────────────────────────────────────────

class ScheduleResponse(BaseModel):
    id: str
    workflow_id: UUID
    user_id: str

    freq: str
    cron: Optional[str]
    time: Optional[str]
    day: Optional[str]

    enabled: bool

    last_run_at: Optional[datetime]
    next_run_at: Optional[datetime]

    run_count: int
    fail_count: int

    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ScheduleWithWorkflow(ScheduleResponse):
    workflow_name: Optional[str] = None

    model_config = {"from_attributes": True}