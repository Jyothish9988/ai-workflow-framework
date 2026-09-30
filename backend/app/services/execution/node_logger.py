"""Per-node DB logging. Every function commits so polling API requests see live progress."""
import traceback  # noqa: F401  (callers pass tracebacks in)

from app.models.workflow_execution import NodeExecutionLog, NodeStatus

from .context import clean_ctx, diff, ms, utcnow
from .state import RunState


async def log_start(state: RunState, node: dict, ctx: dict) -> NodeExecutionLog:
    node_log = NodeExecutionLog(
        execution_id=state.execution_id,
        node_id=node["id"],
        node_type=node["type"],
        node_label=node.get("data", {}).get("label"),
        sequence=state.next_seq(),
        status=NodeStatus.RUNNING,
        input_context=clean_ctx(ctx),
        started_at=utcnow(),
    )
    state.db.add(node_log)
    await state.db.commit()
    return node_log


async def _finish(state, node_log, status, node_start, **fields):
    """Shared tail: set status/timings/extra fields and commit."""
    end = utcnow()
    node_log.status = status
    node_log.completed_at = end
    node_log.duration_ms = ms(node_start, end)
    for k, v in fields.items():
        setattr(node_log, k, v)
    await state.db.commit()


async def log_done(state, node_log, ctx_before, ctx_after, log, handle, node_start):
    await _finish(
        state, node_log, NodeStatus.SUCCESS, node_start,
        log_message=log,
        output_context=clean_ctx(ctx_after),
        context_diff=diff(clean_ctx(ctx_before), clean_ctx(ctx_after)),
        branch_taken=handle,
    )


async def log_fail(state, node_log, msg, exc, tb, node_start):
    await _finish(state, node_log, NodeStatus.FAILED, node_start,
                  log_message=msg, error_message=str(exc), error_traceback=tb)


async def log_cancelled(state, node_log, node_start):
    await _finish(state, node_log, NodeStatus.CANCELLED, node_start, log_message="🛑 Cancelled")


async def log_skipped(state: RunState, node_id: str, nodes: dict) -> None:
    state.nsk += 1
    state.db.add(NodeExecutionLog(
        execution_id=state.execution_id,
        node_id=node_id,
        node_type=nodes.get(node_id, {}).get("type", "unknown"),
        sequence=state.next_seq(),
        status=NodeStatus.SKIPPED,
        log_message="Skipped (already visited in this scope)",
    ))
    await state.db.flush()
