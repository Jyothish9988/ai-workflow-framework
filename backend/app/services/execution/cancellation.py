"""Cancellation support: one asyncio.Event per running execution, looked up by execution id."""
import asyncio

from .signals import CancelledExecution

_cancel_events: dict[str, asyncio.Event] = {}


def register_execution(execution_id) -> asyncio.Event:
    """Create and store a cancel event for this execution."""
    event = asyncio.Event()
    _cancel_events[str(execution_id)] = event
    return event


def cancel_execution(execution_id) -> bool:
    """Signal cancellation (called by the /cancel API). True if the execution was found."""
    event = _cancel_events.get(str(execution_id))
    if event:
        event.set()
        return True
    return False


def deregister_execution(execution_id) -> None:
    """Clean up after an execution finishes."""
    _cancel_events.pop(str(execution_id), None)


def check_cancelled(cancel_event: asyncio.Event | None) -> None:
    """Cheap checkpoint: raise if the cancel flag has been set."""
    if cancel_event and cancel_event.is_set():
        raise CancelledExecution("Execution was cancelled")


async def run_cancellable(coro, cancel_event: asyncio.Event | None):
    """Run a node coroutine but abort it the moment the cancel flag is raised.
    This lets Stop interrupt a slow AI/HTTP call instead of waiting for it."""
    if cancel_event is None:
        return await coro
    task = asyncio.ensure_future(coro)
    waiter = asyncio.ensure_future(cancel_event.wait())
    try:
        done, _ = await asyncio.wait({task, waiter}, return_when=asyncio.FIRST_COMPLETED)
        if task in done:
            return task.result()          # normal finish (re-raises node errors / loop signals)
        task.cancel()                     # cancel flag won: abort the in-flight call
        try:
            await task
        except BaseException:
            pass
        raise CancelledExecution("Execution was cancelled")
    except asyncio.CancelledError:        # server shutting down: don't leave the node running
        task.cancel()
        raise
    finally:
        waiter.cancel()
