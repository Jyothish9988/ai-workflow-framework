"""Leaf (non-branching) node executors and the dispatcher `execute_leaf`.

Every handler has the same signature and returns (new_ctx, log_message, next_handle):
    data  - node data with {{placeholders}} already interpolated
    raw   - node data exactly as stored
"""
from .context import set_nested
from .io_nodes import ai_agent, http_request
from .signals import LoopBreak, LoopContinue
from .wait_node import wait
from .context import interpolate_context


async def _start(data, raw, ctx, cancel):
    return ctx, "🚀 Workflow Started", None


async def _webhook(data, raw, ctx, cancel):
    return ctx, "⚡ Webhook trigger fired", None


async def _message_box(data, raw, ctx, cancel):
    msg = data.get("message", "")
    return set_nested(ctx, "message.text", msg), f"💬 Message: {msg}", None


async def _email(data, raw, ctx, cancel):
    to, subject = data.get("to", ""), data.get("subject", "")
    new_ctx = set_nested(set_nested(ctx, "email.status", "sent"), "email.to", to)
    return new_ctx, f"✉ Email → {to} | {subject}", None


async def _transform(data, raw, ctx, cancel):
    try:
        # NOTE: eval on user-authored text; builtins are stripped but this is not a real sandbox.
        result = eval(data.get("expression", ""), {"input": ctx, "__builtins__": {}})
    except Exception as e:
        raise RuntimeError(f"Transform eval error: {e}") from e
    return set_nested(ctx, "transform.result", result), f"⚙ Transform → {str(result)[:60]}", None


async def _break(data, raw, ctx, cancel):
    raise LoopBreak()


async def _continue(data, raw, ctx, cancel):
    raise LoopContinue()


# node type (lower-cased) -> handler
_HANDLERS = {
    "start": _start, "webhooktrigger": _webhook, "messagebox": _message_box, "email": _email,
    "http_request": http_request, "http-request": http_request,
    "wait": wait, "transform": _transform, "aiagent": ai_agent,
    "break": _break, "continue": _continue,
}


async def execute_leaf(node: dict, ctx: dict, cancel_event=None):
    ntype = node["type"].strip().lower()
    raw = node.get("data", {})
    data = {k: interpolate_context(v, ctx) for k, v in raw.items()}

    handler = _HANDLERS.get(ntype)
    if handler:
        return await handler(data, raw, ctx, cancel_event)

    # Fall back to plugin-style handlers (Gmail, etc.) registered elsewhere.
    from app.services.node_handlers import HANDLERS
    external = HANDLERS.get(ntype)
    if external:
        return await external(data, ctx, set_nested)
    return ctx, f"❓ Unknown node type: {node['type']}", None
