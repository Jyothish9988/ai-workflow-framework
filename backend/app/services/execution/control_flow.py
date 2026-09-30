"""Branching nodes (IF, Loop). Each returns (new_ctx, next_node_id_or_None).

They recurse into the graph through `run`, a callable pre-bound by the engine:
    run(start_id=..., ctx=..., visited=set(), stop_at={...}) -> ctx
This avoids a circular import with execution_engine.
"""
import json

from .cancellation import check_cancelled
from .context import evaluate_condition, interpolate_context, set_nested
from .graph_utils import find_loop_exit, find_merge_node, loop_body_edges
from .node_logger import log_done
from .signals import LoopBreak, LoopContinue


async def run_if(node_id, node, ctx, *, adjacency, state, node_log, node_start, run, **_):
    data = {k: interpolate_context(v, ctx) for k, v in node.get("data", {}).items()}
    field, operator = data.get("field", ""), data.get("operator", "equals")
    expected, expected2 = data.get("value", ""), data.get("value2", "")

    actual = interpolate_context("{{" + field + "}}", ctx)
    result = evaluate_condition(str(actual), operator, str(expected), str(expected2))
    handle = "true" if result else "false"
    new_ctx = set_nested(set_nested(ctx, "if.result", result), "if.branch", handle)

    log = f"🔀 IF {field} {operator} '{expected}' → {handle.upper()}"
    state.append_log(log)
    state.ns += 1
    await log_done(state, node_log, ctx, new_ctx, log, handle, node_start)

    # Run the chosen branch up to (not including) the node where both branches rejoin.
    merge_id = find_merge_node(node_id, adjacency)
    for edge in adjacency.get(node_id, []):
        if edge.get("sourceHandle") == handle:
            new_ctx = await run(start_id=edge["target"], ctx=new_ctx.copy(), visited=set(),
                                stop_at={merge_id} if merge_id else None)
    return new_ctx, merge_id          # engine continues from the merge node


def _resolve_list(items_var: str, ctx: dict) -> list:
    """Look up the list for a For-each loop, e.g. 'gmail.messages' or '{{gmail.messages}}'."""
    if not items_var:
        raise RuntimeError("Loop (For each): set the List path, e.g. gmail.messages")
    path = items_var.strip("{} ").strip()
    value = ctx
    for part in path.split("."):
        value = value.get(part) if isinstance(value, dict) else None
    if isinstance(value, str):        # tolerate a JSON-encoded list
        try:
            value = json.loads(value)
        except Exception:
            pass
    if not isinstance(value, list):
        raise RuntimeError(f"Loop: '{path}' is not a list in the workflow context "
                           f"(found {type(value).__name__})")
    return value


async def run_loop(node_id, node, ctx, *, adjacency, state, node_log, node_start,
                   run, cancel_event, **_):
    raw = node.get("data", {})
    count = int(raw.get("count", 3))
    iter_var = raw.get("iterVar", "loop.item").strip() or "loop.item"

    items: list = []
    if raw.get("loopType", "times") == "forEach":
        items = _resolve_list(str(raw.get("itemsVar", "") or "").strip(), ctx)
        count = len(items)

    child_starts = [e["target"] for e in loop_body_edges(node_id, adjacency)]
    exit_id = find_loop_exit(node_id, adjacency)
    stop_at = {exit_id} if exit_id else None      # body runs must not spill past the loop

    log = f"🔄 Loop {count}× starting  (iter → {{{{{iter_var}}}}})"
    state.append_log(log)
    state.ns += 1
    await log_done(state, node_log, ctx, ctx, log, None, node_start)

    loop_ctx = ctx.copy()
    for i in range(count):
        check_cancelled(cancel_event)             # once per iteration
        iter_ctx = set_nested(set_nested(loop_ctx.copy(), "loop.index", i), "loop.count", count)
        iter_ctx = set_nested(iter_ctx, iter_var, items[i] if items else i)
        state.append_log(f"  ┌─ Iteration {i + 1}/{count}")
        try:
            for start in child_starts:
                iter_ctx = await run(start_id=start, ctx=iter_ctx.copy(), visited=set(), stop_at=stop_at)
        except LoopBreak:
            state.append_log(f"  └─ 🔄 Break at iteration {i + 1}")
            loop_ctx = iter_ctx
            break
        except LoopContinue:
            state.append_log(f"  └─ 🔄 Continue at iteration {i + 1}")
            loop_ctx = iter_ctx
            continue
        state.append_log(f"  └─ ✓ Iteration {i + 1} done")
        loop_ctx = iter_ctx
    return loop_ctx, exit_id          # engine continues from the loop's exit node
