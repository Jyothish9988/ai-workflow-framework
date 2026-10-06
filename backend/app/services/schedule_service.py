import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from croniter import croniter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.db import AsyncSessionLocal
from app.models.scheduled_workflow import ScheduledWorkflow
from app.models.workflow import Workflow
from app.models.workflow_execution import ExecutionStatus, WorkflowExecution
from app.schemas.schedule import ScheduleCreate, ScheduleUpdate
from app.services.run_manager import start_run

log = logging.getLogger("scheduler")


def utcnow():
    return datetime.now(timezone.utc)


# ── Cron helpers ──────────────────────────────────────────────────────────────

def _freq_to_cron(freq: str, time: Optional[str] = "00:00", day: Optional[str] = "1") -> Optional[str]:
    """Convert a human-friendly frequency into a cron expression."""
    if freq in ("manual", "custom"):
        return None
    h, m = (time or "00:00").split(":")
    h, m = int(h), int(m)               # "09:05" -> "9 5" (valid cron either way)
    match freq:
        case "minutely": return "* * * * *"
        case "hourly":   return f"{m} * * * *"
        case "daily":    return f"{m} {h} * * *"
        case "weekly":   return f"{m} {h} * * {day or '1'}"
        case "monthly":  return f"{m} {h} {day or '1'} * *"
    return None


def compute_next_run(cron: Optional[str], tz: Optional[str] = "UTC",
                     base: Optional[datetime] = None) -> Optional[datetime]:
    """Next fire time (UTC, tz-aware) of `cron` evaluated in timezone `tz`, after `base`."""
    if not cron or not croniter.is_valid(cron):
        return None
    base = (base or utcnow()).astimezone(ZoneInfo(tz or "UTC"))
    return croniter(cron, base).get_next(datetime).astimezone(timezone.utc)


def is_one_shot(cron: Optional[str]) -> bool:
    """'m h D M *' with a concrete day AND month is the UI's 'Once' mode: fire once, then disable."""
    parts = (cron or "").split()
    return len(parts) == 5 and parts[2].isdigit() and parts[3].isdigit()


def _refresh_next_run(schedule: ScheduledWorkflow) -> None:
    schedule.next_run_at = (
        compute_next_run(schedule.cron, schedule.timezone)
        if schedule.enabled and schedule.cron else None
    )


# ── CRUD ──────────────────────────────────────────────────────────────────────

async def get_schedule(db: AsyncSession, workflow_id: UUID, user_id) -> Optional[ScheduledWorkflow]:
    result = await db.execute(
        select(ScheduledWorkflow)
        .options(selectinload(ScheduledWorkflow.workflow))
        .where(
            ScheduledWorkflow.workflow_id == workflow_id,
            ScheduledWorkflow.user_id == str(user_id),
        )
        .order_by(ScheduledWorkflow.created_at.desc())
    )
    return result.scalars().first()     # tolerate legacy duplicates instead of raising


async def get_schedule_by_id(db: AsyncSession, schedule_id: UUID, user_id) -> Optional[ScheduledWorkflow]:
    result = await db.execute(
        select(ScheduledWorkflow)
        .options(selectinload(ScheduledWorkflow.workflow))
        .where(
            ScheduledWorkflow.id == str(schedule_id),
            ScheduledWorkflow.user_id == str(user_id),
        )
    )
    return result.scalar_one_or_none()


async def list_schedules(db: AsyncSession, user_id, enabled_only: bool = False) -> list[ScheduledWorkflow]:
    q = (
        select(ScheduledWorkflow)
        .options(selectinload(ScheduledWorkflow.workflow))
        .where(ScheduledWorkflow.user_id == str(user_id))
        .order_by(ScheduledWorkflow.created_at.desc())
    )
    if enabled_only:
        q = q.where(ScheduledWorkflow.enabled == True)  # noqa: E712

    result = await db.execute(q)
    return list(result.scalars().all())


async def upsert_schedule(db: AsyncSession, workflow_id: UUID, user_id, payload: ScheduleCreate) -> ScheduledWorkflow:
    """Create or fully replace the schedule for a workflow (one schedule per workflow)."""
    existing = await get_schedule(db, workflow_id, user_id)

    cron = payload.cron if payload.freq == "custom" else _freq_to_cron(payload.freq, payload.time, payload.day)
    enabled = payload.enabled if payload.freq != "manual" else False

    if existing:
        schedule = existing
    else:
        schedule = ScheduledWorkflow(workflow_id=workflow_id, user_id=str(user_id))
        db.add(schedule)

    schedule.freq = payload.freq
    schedule.cron = cron
    schedule.time = payload.time
    schedule.day = payload.day
    schedule.timezone = payload.timezone
    schedule.enabled = enabled
    schedule.updated_at = utcnow()
    _refresh_next_run(schedule)

    await db.flush()
    return schedule


async def patch_schedule(db: AsyncSession, schedule: ScheduledWorkflow, payload: ScheduleUpdate) -> ScheduledWorkflow:
    """Partially update a schedule. Raises ValueError for an unusable combination."""
    if payload.freq is not None:
        schedule.freq = payload.freq
    if payload.time is not None:
        schedule.time = payload.time
    if payload.day is not None:
        schedule.day = payload.day
    if payload.timezone is not None:
        schedule.timezone = payload.timezone
    if payload.enabled is not None:
        schedule.enabled = payload.enabled

    if schedule.freq == "custom":
        if payload.cron is not None:
            schedule.cron = payload.cron
        if not schedule.cron or not croniter.is_valid(schedule.cron):
            raise ValueError("a valid cron expression is required when freq is 'custom'")
    elif any(f is not None for f in (payload.freq, payload.time, payload.day)):
        schedule.cron = _freq_to_cron(schedule.freq, schedule.time, schedule.day)

    if schedule.freq == "manual":
        schedule.enabled = False
        schedule.cron = None

    schedule.updated_at = utcnow()
    _refresh_next_run(schedule)         # re-arm from "now" so enabling never back-fires old slots
    await db.flush()
    return schedule


async def delete_schedule(db: AsyncSession, schedule: ScheduledWorkflow) -> None:
    await db.delete(schedule)
    await db.flush()


async def record_run(db: AsyncSession, schedule: ScheduledWorkflow, success: bool) -> None:
    """Update run tracking counters after an execution."""
    schedule.last_run_at = utcnow()
    schedule.run_count += 1
    if not success:
        schedule.fail_count += 1
    await db.flush()


# ── Running a schedule's workflow ─────────────────────────────────────────────

async def finalize_run(schedule_id: str, execution_id: str) -> None:
    """Called when a run started by a schedule has finished: record its outcome."""
    async with AsyncSessionLocal() as db:
        execution = await db.get(WorkflowExecution, UUID(execution_id))
        schedule = await db.get(ScheduledWorkflow, schedule_id)
        if not execution or not schedule:
            return
        if execution.status == ExecutionStatus.FAILED:
            schedule.fail_count += 1
            schedule.last_error = (execution.error_message or "Workflow run failed")[:2000]
        elif execution.status == ExecutionStatus.PARTIAL:
            schedule.last_error = (execution.error_message or "Some nodes failed")[:2000]
        else:
            schedule.last_error = None
        await db.commit()


async def dispatch_run(db: AsyncSession, schedule: ScheduledWorkflow) -> str:
    """Start the schedule's workflow in the background (non-blocking, honours the concurrency cap).
    Used by both the cron worker and 'Run now'. Returns the execution id.
    Raises ValueError (nothing to run), RunnerBusy, or RuntimeError (invalid workflow)."""
    wf = await db.get(Workflow, schedule.workflow_id)
    if not wf or not wf.workflow_json:
        raise ValueError("Workflow is missing or has no nodes")

    schedule_id = schedule.id

    async def _done(execution_id: str):
        await finalize_run(schedule_id, execution_id)

    execution_id = await start_run(wf.workflow_json, wf.id, wf.user_id, on_done=_done)

    schedule.last_run_at = utcnow()
    schedule.run_count += 1
    schedule.last_execution_id = execution_id
    schedule.last_error = None
    return execution_id