from __future__ import annotations

import re
from datetime import datetime
from typing import Optional
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter
from pydantic import BaseModel, field_validator, model_validator

FREQS = {"manual", "minutely", "hourly", "daily", "weekly", "monthly", "custom"}
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _check_freq(v: Optional[str]) -> Optional[str]:
    if v is not None and v not in FREQS:
        raise ValueError(f"freq must be one of {sorted(FREQS)}")
    return v


def _check_tz(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    try:
        ZoneInfo(v)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        raise ValueError(f"unknown timezone '{v}' (use an IANA name like 'Asia/Kolkata')")
    return v


def _check_time(v: Optional[str]) -> Optional[str]:
    if v is not None and not _TIME_RE.match(v):
        raise ValueError("time must be HH:MM (24h)")
    return v


def _check_cron(v: Optional[str]) -> Optional[str]:
    if v is not None:
        v = v.strip()
        if not croniter.is_valid(v):
            raise ValueError(f"invalid cron expression: '{v}'")
    return v


# ── Request schemas ───────────────────────────────────────────────────────────

class ScheduleCreate(BaseModel):
    freq: str = "manual"
    cron: Optional[str] = None
    time: Optional[str] = None
    day: Optional[str] = None
    timezone: str = "UTC"
    enabled: bool = True

    @field_validator("freq")
    @classmethod
    def _v_freq(cls, v):
        return _check_freq(v)

    @field_validator("timezone")
    @classmethod
    def _v_tz(cls, v):
        return _check_tz(v)

    @field_validator("time")
    @classmethod
    def _v_time(cls, v):
        return _check_time(v)

    @field_validator("cron")
    @classmethod
    def _v_cron(cls, v):
        return _check_cron(v)

    # NOTE: a field_validator on `cron` never runs when cron is omitted (default None),
    # so the "custom needs a cron" rule has to be a model-level check.
    @model_validator(mode="after")
    def cron_required_for_custom(self):
        if self.freq == "custom" and not self.cron:
            raise ValueError("cron expression is required when freq is 'custom'")
        return self


class ScheduleUpdate(BaseModel):
    freq: Optional[str] = None
    cron: Optional[str] = None
    time: Optional[str] = None
    day: Optional[str] = None
    timezone: Optional[str] = None
    enabled: Optional[bool] = None

    @field_validator("freq")
    @classmethod
    def _v_freq(cls, v):
        return _check_freq(v)

    @field_validator("timezone")
    @classmethod
    def _v_tz(cls, v):
        return _check_tz(v)

    @field_validator("time")
    @classmethod
    def _v_time(cls, v):
        return _check_time(v)

    @field_validator("cron")
    @classmethod
    def _v_cron(cls, v):
        return _check_cron(v)


# ── Response schemas ──────────────────────────────────────────────────────────

class ScheduleResponse(BaseModel):
    id: str
    workflow_id: UUID
    user_id: str

    freq: str
    cron: Optional[str]
    time: Optional[str]
    day: Optional[str]
    timezone: str = "UTC"

    enabled: bool

    last_run_at: Optional[datetime]
    next_run_at: Optional[datetime]

    run_count: int
    fail_count: int

    last_execution_id: Optional[str] = None
    last_error: Optional[str] = None

    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ScheduleWithWorkflow(ScheduleResponse):
    workflow_name: Optional[str] = None

    model_config = {"from_attributes": True}