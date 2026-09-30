"""Wait node: fixed/dynamic delay with optional jitter, cap, and early-exit condition."""
import asyncio
import random

from .cancellation import check_cancelled
from .context import interpolate_context, set_nested


async def _interruptible_sleep(seconds: float, cancel_event) -> None:
    """Sleep, but wake immediately (and raise) if the execution is cancelled."""
    if not cancel_event:
        await asyncio.sleep(seconds)
        return
    try:
        await asyncio.wait_for(cancel_event.wait(), timeout=seconds)
        check_cancelled(cancel_event)      # event fired before timeout -> cancelled
    except asyncio.TimeoutError:
        pass                               # normal path: slept the full time


def _to_float(value, default=None):
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _compute_seconds(data: dict) -> float:
    mult = {"seconds": 1, "minutes": 60, "hours": 3600}.get(data.get("unit", "seconds"), 1)
    base = float(data.get("seconds", 1)) * mult

    dynamic = _to_float(str(data.get("dynamicValue", "")).strip())   # overrides the base value
    if dynamic is not None:
        base = dynamic
    cap = _to_float(data.get("maxCap", ""))
    if cap is not None:
        base = min(base, cap)

    jitter = 0.0
    if data.get("jitter"):
        jitter = (_to_float(data.get("jitterPercent", 0), 0.0)) / 100.0
    return max(0, round(base * (1 + random.uniform(-jitter, jitter)), 3))


async def wait(data: dict, raw: dict, ctx: dict, cancel_event):
    seconds = _compute_seconds(data)
    condition = str(data.get("exitCondition", "")).strip()
    exit_reason, elapsed = "elapsed", seconds

    if condition:
        # Poll the condition until it becomes true or the deadline passes.
        loop = asyncio.get_running_loop()
        poll = max(0.1, float(data.get("pollInterval", 1)))
        deadline = loop.time() + seconds
        while loop.time() < deadline:
            check_cancelled(cancel_event)
            try:
                # NOTE: eval on user-authored text; builtins are stripped but this is not a real sandbox.
                if eval(interpolate_context(condition, ctx), {"__builtins__": {}}):
                    exit_reason = "condition_met"
                    elapsed = round(loop.time() - (deadline - seconds), 3)
                    break
            except Exception:
                pass
            await asyncio.sleep(min(poll, deadline - loop.time()))
    else:
        await _interruptible_sleep(seconds, cancel_event)

    new_ctx = set_nested(ctx, data.get("outputVar", "wait.elapsed"), elapsed)
    new_ctx = set_nested(new_ctx, "wait.exit_reason", exit_reason)
    new_ctx = set_nested(new_ctx, "wait.requested", seconds)
    return new_ctx, f"⏱ Waited {elapsed}s ({exit_reason})", None
