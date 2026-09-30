"""Workflow execution engine: walks the node graph and records every step to the DB.

Layout (all helpers live in app/services/execution/):
    signals.py       LoopBreak / LoopContinue / CancelledExecution
    cancellation.py  cancel registry + cancellable runner
    context.py       ctx helpers: interpolation, set_nested, conditions
    node_logger.py   NodeExecutionLog DB writes
    graph_utils.py   merge-node / loop-exit detection
    leaf_nodes.py    executors for simple nodes (+ io_nodes.py, wait_node.py)
    control_flow.py  IF and Loop nodes
"""
import traceback
from functools import partial
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workflow_execution import ExecutionStatus, WorkflowExecution
from app.services.execution import node_logger as nlog
from app.services.execution.cancellation import (  # noqa: F401  (re-exported for the API layer)
    cancel_execution, check_cancelled, deregister_execution, register_execution, run_cancellable,
)
from app.services.execution.context import clean_ctx, ms, utcnow
from app.services.execution.control_flow import run_if, run_loop
from app.services.execution.leaf_nodes import execute_leaf
from app.services.execution.signals import CancelledExecution, LoopBreak, LoopContinue  # noqa: F401
from app.services.execution.state import RunState

CONTROL_NODES = {"if": run_if, "loop": run_loop}    # branching nodes handled by control_flow.py


async def execute_graph(
    *, start_id: str, nodes: dict, adjacency: dict, ctx: dict, state: RunState,
    visited: set | None = None, stop_at: set | None = None, cancel_event=None,
) -> dict:
    """Run nodes breadth-first from `start_id`. Recursion happens for IF branches / loop bodies.
    `visited` guards against re-running a node in this scope; `stop_at` marks nodes that belong to the caller."""
    visited = set() if visited is None else visited
    queue, final_ctx = [(start_id, ctx)], ctx
    # Pre-bound recursive runner handed to IF/Loop handlers.
    run = partial(execute_graph, nodes=nodes, adjacency=adjacency, state=state, cancel_event=cancel_event)

    while queue:
        node_id, ctx = queue.pop(0)
        check_cancelled(cancel_event)                       # cancellation checkpoint at every node
        if stop_at and node_id in stop_at:
            continue
        if node_id in visited:
            await nlog.log_skipped(state, node_id, nodes)
            continue
        visited.add(node_id)

        node = nodes.get(node_id)
        if not node:
            state.append_log(f"⚠ Node {node_id} not found, skipping")
            state.nf += 1
            state.error = True
            continue

        ntype = node["type"].strip().lower()
        node_start = utcnow()
        node_log = await nlog.log_start(state, node, ctx)

        # ── Branching nodes (IF / Loop) ──────────────────────────────────────
        if ntype in CONTROL_NODES:
            try:
                final_ctx, next_id = await CONTROL_NODES[ntype](
                    node_id, node, ctx, adjacency=adjacency, state=state, node_log=node_log,
                    node_start=node_start, run=run, cancel_event=cancel_event)
                if next_id and next_id in nodes:            # continue after merge / loop exit
                    queue.append((next_id, final_ctx))
            except CancelledExecution:
                await nlog.log_cancelled(state, node_log, node_start)
                raise
            except (LoopBreak, LoopContinue):
                raise                                       # Break/Continue inside an IF: let the loop handle it
            except Exception as e:
                msg = f"❌ {ntype.upper()} node crashed: {e}"
                state.append_log(msg)
                state.nf += 1
                state.error = True
                await nlog.log_fail(state, node_log, msg, e, traceback.format_exc(), node_start)
            continue

        # ── Leaf nodes ───────────────────────────────────────────────────────
        next_handle = None
        try:
            result_ctx, log, next_handle = await run_cancellable(
                execute_leaf(node, ctx, cancel_event), cancel_event)
            state.append_log(log)
            state.ns += 1
            final_ctx = result_ctx
            await nlog.log_done(state, node_log, ctx, result_ctx, log, next_handle, node_start)
        except CancelledExecution:
            await nlog.log_cancelled(state, node_log, node_start)
            raise
        except (LoopBreak, LoopContinue) as sig:
            state.ns += 1
            label = "🔄 Break" if isinstance(sig, LoopBreak) else "🔄 Continue"
            await nlog.log_done(state, node_log, ctx, ctx, label, None, node_start)
            raise                                           # caught by the enclosing loop
        except Exception as e:
            msg = f"❌ Node {node.get('type', node_id)} crashed: {e}"
            state.append_log(msg)
            state.nf += 1
            state.error = True
            result_ctx, next_handle = ctx, None             # keep going with the old context
            await nlog.log_fail(state, node_log, msg, e, traceback.format_exc(), node_start)

        # Queue successors (respect the handle a node chose, skip nodes owned by the caller).
        for edge in adjacency.get(node_id, []):
            handle = edge.get("sourceHandle")
            if next_handle and handle and handle != next_handle:
                continue
            if stop_at and edge["target"] in stop_at:
                continue
            queue.append((edge["target"], result_ctx.copy()))

    return final_ctx


async def execute_workflow(
    workflow_json: dict, context: dict, db: AsyncSession, workflow_id: UUID, user_id: UUID,
    started: "asyncio.Future | None" = None,   # noqa: F821
) -> list[str]:
    """Public entry point. `started` (optional) is resolved with the execution id once the run
    row is committed, or failed with RuntimeError if validation fails (used by run_manager)."""

    def _early(msg: str) -> list[str]:
        if started is not None and not started.done():
            started.set_exception(RuntimeError(msg))
        return [msg]

    # ── Validate ─────────────────────────────────────────────────────────────
    nodes_list, edges = workflow_json.get("nodes", []), workflow_json.get("edges", [])
    if not nodes_list:
        return _early("❌ No nodes found")
    start_nodes = [n for n in nodes_list if n["type"] == "start"]
    if not start_nodes:
        return _early("❌ Workflow must contain a Start node")
    if len(start_nodes) > 1:
        return _early("❌ Workflow can contain only one Start node")

    nodes = {n["id"]: n for n in nodes_list}
    adjacency: dict[str, list[dict]] = {}
    for e in edges:
        adjacency.setdefault(e["source"], []).append(
            {"target": e["target"], "sourceHandle": e.get("sourceHandle")})

    # ── Create the execution row ─────────────────────────────────────────────
    context["__db__"] = db
    execution = WorkflowExecution(
        workflow_id=str(workflow_id), user_id=str(user_id), status=ExecutionStatus.RUNNING,
        initial_context=clean_ctx(context), started_at=utcnow(), nodes_total=len(nodes_list))
    db.add(execution)
    await db.flush()
    context["__execution__"] = execution      # lets the API return the execution id
    context["__user_id__"] = str(user_id)     # lets Gmail/app nodes find the current user
    await db.commit()                         # run is now visible to /executions and /cancel

    cancel_event = register_execution(str(execution.id))
    if started is not None and not started.done():
        started.set_result(str(execution.id))

    # ── Run ──────────────────────────────────────────────────────────────────
    state, final_ctx = RunState(db=db, execution_id=execution.id), context.copy()
    try:
        final_ctx = await execute_graph(
            start_id=start_nodes[0]["id"], nodes=nodes, adjacency=adjacency,
            ctx=context.copy(), state=state, cancel_event=cancel_event)
        state.append_log("─" * 40)
        state.append_log("✅ Workflow completed")
        execution.status = (
            ExecutionStatus.FAILED if state.error and state.ns == 0 else
            ExecutionStatus.PARTIAL if state.error else
            ExecutionStatus.SUCCESS)
    except CancelledExecution:
        state.append_log("─" * 40)
        state.append_log("🛑 Workflow cancelled by user")
        execution.status = ExecutionStatus.CANCELLED
    finally:
        deregister_execution(str(execution.id))    # always clean up the cancel event

    # ── Persist totals ───────────────────────────────────────────────────────
    execution.completed_at = utcnow()
    execution.duration_ms = ms(execution.started_at, execution.completed_at)
    execution.final_context = clean_ctx(final_ctx)
    execution.nodes_success, execution.nodes_failed, execution.nodes_skipped = state.ns, state.nf, state.nsk
    await db.flush()
    return state.logs
