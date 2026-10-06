"""Runs workflows in the background so /execute can return immediately
(the browser then polls, and the Stop button can cancel a live run)."""
import asyncio
import copy
import traceback
from typing import Awaitable, Callable, Optional

from sqlalchemy import update

from app.database.db import AsyncSessionLocal
from app.models.workflow_execution import ExecutionStatus, WorkflowExecution
from app.services.execution_engine import execute_workflow

MAX_CONCURRENT_RUNS = 20
_tasks: set[asyncio.Task] = set()


class RunnerBusy(RuntimeError):
    """Raised when MAX_CONCURRENT_RUNS is reached. Callers may retry later."""


async def start_run(
    workflow_json: dict,
    workflow_id,
    user_id,
    on_done: Optional[Callable[[str], Awaitable[None]]] = None,
) -> str:
    """Start a run in the background and return its execution id.

    `on_done(execution_id)` (optional) is awaited after the run has finished and been
    committed, whether it succeeded or failed - used by schedules to record the outcome.
    Raises RuntimeError if the workflow is invalid, RunnerBusy if the server is busy."""
    if len(_tasks) >= MAX_CONCURRENT_RUNS:
        raise RunnerBusy("Too many workflows are running right now, try again shortly")

    workflow_json = copy.deepcopy(workflow_json)
    started: asyncio.Future = asyncio.get_running_loop().create_future()

    async def _notify_done():
        if on_done is None or not started.done() or started.exception() is not None:
            return
        try:
            await on_done(started.result())
        except Exception:
            traceback.print_exc()

    async def _runner():
        async with AsyncSessionLocal() as db:          # own session: the request's one closes
            try:
                await execute_workflow(workflow_json, {}, db, workflow_id, user_id, started=started)
                await db.commit()
            except Exception as e:                     # never leave a run stuck as "running"
                await db.rollback()
                traceback.print_exc()
                if not started.done():
                    started.set_exception(e)
                else:
                    await db.execute(
                        update(WorkflowExecution)
                        .where(WorkflowExecution.id == started.result())
                        .values(status=ExecutionStatus.FAILED, error_message=f"Engine error: {e}")
                    )
                    await db.commit()
        await _notify_done()

    task = asyncio.create_task(_runner())
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return await started


async def mark_orphaned_runs() -> None:
    """Call once at startup: runs that were 'running' when the server stopped can never finish."""
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(WorkflowExecution)
            .where(WorkflowExecution.status == ExecutionStatus.RUNNING)
            .values(status=ExecutionStatus.FAILED, error_message="Server restarted while this run was in progress")
        )
        await db.commit()