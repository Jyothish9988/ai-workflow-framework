"""Nodes that talk to the outside world: HTTP requests and the AI agent."""
import json

import httpx

from .context import set_nested


async def http_request(data: dict, raw: dict, ctx: dict, cancel_event):
    method = data.get("method", "GET").upper()
    url = data.get("url", "")
    body = data.get("body")

    try:
        headers = json.loads(data.get("headers") or "{}")
    except Exception:
        headers = {}

    kwargs = {"method": method, "url": url, "headers": headers, "timeout": 15}
    if body:
        if isinstance(body, str):
            try:
                kwargs["json"] = json.loads(body)    # valid JSON string -> send as JSON
            except Exception:
                kwargs["content"] = body             # otherwise send raw text
        elif isinstance(body, dict):
            kwargs["json"] = body
        else:
            kwargs["content"] = body

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.request(**kwargs)
    except Exception as e:
        raise RuntimeError(f"HTTP {method} {url} failed: {e}") from e

    try:
        resp_body = resp.json()
    except Exception:
        resp_body = resp.text

    new_ctx = set_nested(ctx, "http.status", resp.status_code)
    new_ctx = set_nested(new_ctx, "http.body", resp_body)
    new_ctx = set_nested(new_ctx, "http.headers", dict(resp.headers))
    return new_ctx, f"🌐 {method} {url} → {resp.status_code}", None


async def ai_agent(data: dict, raw: dict, ctx: dict, cancel_event):
    from app.services.llm_service import LLMService, LLMResult   # lazy: heavy import

    output_var = data.get("outputVar", "ai.output")
    on_error = data.get("onError", "throw")          # throw | continue | fallback

    db_session = ctx.get("__db__")
    if not db_session:
        raise RuntimeError("No DB session in execution context")

    result = None
    try:
        result = await LLMService(db=db_session).run(
            connection_id=raw.get("connectionId"),   # raw: the id must not be interpolated
            system_prompt=data.get("systemPrompt", "You are a helpful assistant."),
            user_message=data.get("userMessage", data.get("prompt", "")),
            max_tokens=int(data.get("maxTokens", 1024)),
            temperature=float(data.get("temperature", 0.7)),
            response_format=data.get("responseFormat", "text"),
            json_schema=data.get("jsonSchema", ""),
        )
    except Exception:
        if on_error == "fallback":
            result = LLMResult(text=data.get("fallbackText", ""), tokens=0,
                               finish_reason="fallback", model="none", provider="none")
        elif on_error != "continue":
            raise                                    # "continue" leaves result=None

    r = result
    new_ctx = set_nested(ctx, output_var, r.text if r else "")
    new_ctx = set_nested(new_ctx, "ai.model", r.model if r else "")
    new_ctx = set_nested(new_ctx, "ai.provider", r.provider if r else "")
    new_ctx = set_nested(new_ctx, "ai.tokens", r.tokens if r else 0)
    new_ctx = set_nested(new_ctx, "ai.finish_reason", r.finish_reason if r else "error")
    log = (f"🧠 AI Agent ({r.provider}/{r.model}) → {output_var}" if r
           else "🧠 AI Agent → skipped (on_error=continue)")
    return new_ctx, log, None
