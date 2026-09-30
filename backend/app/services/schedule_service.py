from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.scheduled_workflow import ScheduledWorkflow
from app.schemas.schedule import ScheduleCreate, ScheduleUpdate


def utcnow():
    return datetime.now(timezone.utc)


def _freq_to_cron(freq: str, time: Optional[str] = "00:00", day: Optional[str] = "1") -> Optional[str]:
    """Convert a human-friendly frequency into a cron expression."""
    if freq in ("manual", "custom"):
        return None
    h, m = (time or "00:00").split(":")
    match freq:
        case "minutely": return "* * * * *"
        case "hourly":   return f"{m} * * * *"
        case "daily":    return f"{m} {h} * * *"
        case "weekly":   return f"{m} {h} * * {day or '1'}"
        case "monthly":  return f"{m} {h} {day or '1'} * *"
    return None


# ── CRUD ──────────────────────────────────────────────────────────────────────

async def get_schedule(
    db: AsyncSession,
    workflow_id: UUID,
    user_id: UUID,
) -> Optional[ScheduledWorkflow]:
    result = await db.execute(
        select(ScheduledWorkflow)
        .options(selectinload(ScheduledWorkflow.workflow))
        .where(
            ScheduledWorkflow.workflow_id == str(workflow_id),
            ScheduledWorkflow.user_id     == str(user_id),
        )
    )
    return result.scalar_one_or_none()


async def get_schedule_by_id(
    db: AsyncSession,
    schedule_id: UUID,
    user_id: UUID,
) -> Optional[ScheduledWorkflow]:
    result = await db.execute(
        select(ScheduledWorkflow)
        .options(selectinload(ScheduledWorkflow.workflow))
        .where(
            ScheduledWorkflow.id      == str(schedule_id),
            ScheduledWorkflow.user_id == str(user_id),
        )
    )
    return result.scalar_one_or_none()


async def list_schedules(
    db: AsyncSession,
    user_id: UUID,
    enabled_only: bool = False,
) -> list[ScheduledWorkflow]:
    q = (
        select(ScheduledWorkflow)
        .options(selectinload(ScheduledWorkflow.workflow))
        .where(ScheduledWorkflow.user_id == str(user_id))
        .order_by(ScheduledWorkflow.created_at.desc())
    )
    if enabled_only:
        q = q.where(ScheduledWorkflow.enabled == True)

    result = await db.execute(q)
    return list(result.scalars().all())


async def upsert_schedule(
    db: AsyncSession,
    workflow_id: UUID,
    user_id: UUID,
    payload: ScheduleCreate,
) -> ScheduledWorkflow:
    """Create or fully replace the schedule for a workflow."""
    existing = await get_schedule(db, workflow_id, user_id)

    # Resolve cron if not custom
    resolved_cron = (
        payload.cron
        if payload.freq == "custom"
        else _freq_to_cron(payload.freq, payload.time, payload.day)
    )

    if existing:
        existing.freq       = payload.freq
        existing.cron       = resolved_cron
        existing.time       = payload.time
        existing.day        = payload.day
        existing.enabled    = payload.enabled if payload.freq != "manual" else False
        existing.updated_at = utcnow()
        await db.flush()
        return existing

    schedule = ScheduledWorkflow(
        workflow_id = str(workflow_id),
        user_id     = str(user_id),
        freq        = payload.freq,
        cron        = resolved_cron,
        time        = payload.time,
        day         = payload.day,
        enabled     = payload.enabled if payload.freq != "manual" else False,
    )
    db.add(schedule)
    await db.flush()
    return schedule


async def patch_schedule(
    db: AsyncSession,
    schedule: ScheduledWorkflow,
    payload: ScheduleUpdate,
) -> ScheduledWorkflow:
    """Partially update a schedule."""
    if payload.freq is not None:
        schedule.freq = payload.freq
    if payload.time is not None:
        schedule.time = payload.time
    if payload.day is not None:
        schedule.day = payload.day
    if payload.enabled is not None:
        schedule.enabled = payload.enabled

    # Re-resolve cron whenever freq/time/day change
    if any(f is not None for f in [payload.freq, payload.time, payload.day]):
        schedule.cron = (
            payload.cron
            if schedule.freq == "custom"
            else _freq_to_cron(schedule.freq, schedule.time, schedule.day)
        )

    if schedule.freq == "manual":
        schedule.enabled = False

    schedule.updated_at = utcnow()
    await db.flush()
    return schedule


async def delete_schedule(
    db: AsyncSession,
    schedule: ScheduledWorkflow,
) -> None:
    await db.delete(schedule)
    await db.flush()


async def record_run(
    db: AsyncSession,
    schedule: ScheduledWorkflow,
    success: bool,
) -> None:
    """Update run tracking counters after an execution."""
    schedule.last_run_at = utcnow()
    schedule.run_count  += 1
    if not success:
        schedule.fail_count += 1
    await db.flush()