"""Tiny in-process cron runner for /schedules. Run uvicorn with ONE worker."""
import asyncio
from datetime import datetime, timezone
from uuid import UUID

from croniter import croniter
from sqlalchemy import select

from app.database.db import AsyncSessionLocal
from app.models.scheduled_workflow import ScheduledWorkflow
from app.models.workflow import Workflow
from app.services.execution_engine import execute_workflow
from app.services.schedule_service import record_run


async def _tick():
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(ScheduledWorkflow).where(ScheduledWorkflow.enabled == True, ScheduledWorkflow.cron.isnot(None))  # noqa: E712
        )).scalars().all()
        for s in rows:
            if not croniter.is_valid(s.cron):
                continue
            base = max(t for t in (s.last_run_at, s.updated_at, s.created_at) if t)
            nxt = croniter(s.cron, base).get_next(datetime)
            s.next_run_at = nxt
            if nxt > now:
                continue
            ok = True
            try:
                wf = await db.get(Workflow, UUID(str(s.workflow_id)))
                if not wf or not wf.workflow_json:
                    raise RuntimeError("workflow missing or empty")
                await execute_workflow(wf.workflow_json, {}, db, wf.id, UUID(str(s.user_id)))
            except Exception as e:  # keep the loop alive
                ok = False
                print(f"[scheduler] {s.id} failed: {e}")
            await record_run(db, s, ok)
            s.next_run_at = croniter(s.cron, now).get_next(datetime)
        await db.commit()


async def scheduler_loop(interval: int = 20):
    while True:
        try:
            await _tick()
        except Exception as e:
            print(f"[scheduler] tick error: {e}")
        await asyncio.sleep(interval)
