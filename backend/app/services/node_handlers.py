"""Extra node types. Each handler: async (data, ctx, set_nested) -> (new_ctx, log, branch_handle|None).
`data` is already {{variable}}-interpolated by the engine."""
import json
import re
from datetime import datetime, timedelta, timezone

import httpx


def _get(ctx: dict, path: str):
    cur = ctx
    for p in str(path).strip().split("."):
        cur = cur.get(p) if isinstance(cur, dict) else None
    return cur


async def noop(data, ctx, sn):
    return ctx, "No-op (pass-through)", None


async def set_fields(data, ctx, sn):
    out = ctx
    for f in data.get("fields") or []:
        if f.get("key"):
            out = sn(out, f["key"], f.get("value", ""))
    return out, f"Set {len(data.get('fields') or [])} field(s)", None


async def switch(data, ctx, sn):
    value = str(data.get("value", ""))
    rules = [str(r) for r in (data.get("rules") or [])]
    handle = next((f"case_{i}" for i, r in enumerate(rules) if r == value), "fallback")
    return sn(ctx, "switch.branch", handle), f"Switch '{value}' -> {handle}", handle


async def text(data, ctx, sn):
    var = data.get("outputVar") or "text.output"
    return sn(ctx, var, data.get("template", "")), f"Text -> {var}", None


async def json_node(data, ctx, sn):
    op = data.get("operation", "parse")
    var = data.get("outputVar") or "json.result"
    source = data.get("source", "")

    val = _get(ctx, source)

    # Debug / validation
    if val is None:
        raise ValueError(
            f"JSON node source '{source}' returned None. "
            f"Check whether the source variable exists in workflow context."
        )

    if op == "parse":
        if isinstance(val, str):
            val = val.strip()

            if not val:
                raise ValueError(
                    f"JSON node source '{source}' is empty."
                )

            try:
                res = json.loads(val)
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"Invalid JSON in source '{source}': {e}"
                ) from e
        else:
            # Already parsed JSON
            res = val

    elif op == "stringify":
        res = json.dumps(val, default=str)

    elif op == "extract":
        res = val

        for p in filter(
            None,
            re.split(r"[.\[\]]", str(data.get("path", "")))
        ):
            if isinstance(res, list) and p.isdigit():
                index = int(p)

                if index >= len(res):
                    raise ValueError(
                        f"JSON path index {index} is out of range."
                    )

                res = res[index]

            elif isinstance(res, dict):
                if p not in res:
                    raise ValueError(
                        f"JSON path '{p}' was not found."
                    )

                res = res[p]

            else:
                res = None
                break

    else:
        raise ValueError(f"Unsupported JSON operation: {op}")

    return sn(ctx, var, res), f"JSON {op} -> {var}", None


async def regex(data, ctx, sn):
    src, pat, mode = str(data.get("source", "")), data.get("pattern", ""), data.get("mode", "match")
    var = data.get("outputVar") or "regex.result"
    if mode == "replace":
        res = re.sub(pat, data.get("replacement", ""), src)
    elif mode == "match_all":
        res = re.findall(pat, src)
    else:
        m = re.search(pat, src)
        res = (m.group(1) if m and m.groups() else m.group(0)) if m else None
    return sn(ctx, var, res), f"Regex {mode} -> {var}", None


async def datetime_node(data, ctx, sn):
    op, var = data.get("operation", "now"), data.get("outputVar") or "datetime.result"
    fmt = data.get("format") or "%Y-%m-%d %H:%M:%S"
    base = datetime.now(timezone.utc)
    if op != "now" and data.get("value"):
        base = datetime.fromisoformat(str(data["value"]))
    if op in ("add", "subtract"):
        delta = timedelta(**{data.get("unit", "days"): float(data.get("amount") or 0)})
        base = base + delta if op == "add" else base - delta
    return sn(ctx, var, base.strftime(fmt)), f"Date {op} -> {var}", None


async def _post(url, payload, name, ctx, sn):
    if not url:
        raise RuntimeError(f"{name}: URL/token missing")
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(url, json=payload)
    if r.status_code >= 400:
        raise RuntimeError(f"{name} failed: {r.status_code} {r.text[:200]}")
    return sn(ctx, f"{name}.status", r.status_code), f"{name} message sent ({r.status_code})", None


async def slack(d, ctx, sn):
    return await _post(d.get("webhookUrl"), {"text": d.get("text", "")}, "slack", ctx, sn)


async def discord(d, ctx, sn):
    p = {"content": d.get("text", "")}
    if d.get("username"):
        p["username"] = d["username"]
    return await _post(d.get("webhookUrl"), p, "discord", ctx, sn)


async def telegram(d, ctx, sn):
    tok = d.get("botToken")
    url = f"https://api.telegram.org/bot{tok}/sendMessage" if tok else None
    return await _post(url, {"chat_id": d.get("chatId"), "text": d.get("text", "")}, "telegram", ctx, sn)


HANDLERS = {
    "noop": noop, "set": set_fields, "switch": switch, "text": text, "json": json_node,
    "regex": regex, "datetime": datetime_node, "slack": slack, "discord": discord, "telegram": telegram,
}

# Gmail nodes
from app.services.gmail_nodes import GMAIL_HANDLERS
HANDLERS.update(GMAIL_HANDLERS)
