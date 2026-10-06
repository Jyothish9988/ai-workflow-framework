"""Tiny in-process cron runner for /schedules.

Started from the app lifespan in main.py. Rows are claimed with SELECT ... FOR UPDATE
SKIP LOCKED, so running several uvicorn workers will not double-fire a schedule."""
import asyncio
import logging

from croniter import croniter
from sqlalchemy import select

from app.database.db import AsyncSessionLocal
from app.models.scheduled_workflow import ScheduledWorkflow
from app.services.run_manager import RunnerBusy
from app.services.schedule_service import (
    compute_next_run,
    dispatch_run,
    is_one_shot,
    utcnow,
)

log = logging.getLogger("scheduler")


async def _tick():
    now = utcnow()
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(ScheduledWorkflow)
            .where(ScheduledWorkflow.enabled == True, ScheduledWorkflow.cron.isnot(None))  # noqa: E712
            .with_for_update(skip_locked=True, of=ScheduledWorkflow)
        )).scalars().all()

        for s in rows:
            tz = s.timezone or "UTC"

            if not croniter.is_valid(s.cron):
                s.enabled = False
                s.next_run_at = None
                s.last_error = f"Disabled: invalid cron expression '{s.cron}'"
                continue

            # Legacy rows / rows created before the worker saw them: arm, don't fire.
            if s.next_run_at is None:
                s.next_run_at = compute_next_run(s.cron, tz, now)
                continue

            if s.next_run_at > now:
                continue

            # ── Due ──────────────────────────────────────────────────────────
            try:
                await dispatch_run(db, s)
            except RunnerBusy:
                continue                        # leave it due; retry on the next tick
            except Exception as e:              # missing workflow, invalid graph, ...
                log.warning("schedule %s failed to start: %s", s.id, e)
                s.last_run_at = now
                s.run_count += 1
                s.fail_count += 1
                s.last_error = str(e)[:2000]

            if is_one_shot(s.cron):
                s.enabled = False               # "Once" must not recur next year
                s.next_run_at = None
            else:
                # Missed slots (server was down) collapse into this single run.
                s.next_run_at = compute_next_run(s.cron, tz, now)

        await db.commit()


async def scheduler_loop(interval: int = 20):
    while True:
        try:
            await _tick()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.exception("tick error: %s", e)
        await asyncio.sleep(interval)