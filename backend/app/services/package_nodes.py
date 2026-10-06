
import json
import re
from urllib.parse import quote
from uuid import UUID

import httpx
from sqlalchemy import select

FIELD_TYPES = {"text", "textarea", "code", "number", "select", "toggle", "secret"}
METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
_VAR = re.compile(r"\$\{(\w+)\}")
_UUID = re.compile(r"[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{12}")
_URL = re.compile(r"^https?://[^/${}\s]+")          # scheme + host with no placeholder


def validate_manifest(m: dict) -> dict:
    """Return the cleaned manifest or raise ValueError with a readable message."""
    if not isinstance(m, dict):
        raise ValueError("Manifest must be a JSON object")
    name = str(m.get("name", "")).strip()
    if not 2 <= len(name) <= 60:
        raise ValueError("name must be 2-60 characters")
    fields, seen = m.get("fields") or [], set()
    if not isinstance(fields, list) or len(fields) > 30:
        raise ValueError("fields must be a list (max 30)")
    for f in fields:
        k = str(f.get("key", ""))
        if not re.fullmatch(r"[A-Za-z_]\w{0,40}", k) or k in seen:
            raise ValueError(f"Invalid or duplicate field key: '{k}'")
        if f.get("type", "text") not in FIELD_TYPES:
            raise ValueError(f"Field '{k}': type must be one of {sorted(FIELD_TYPES)}")
        seen.add(k)
    ops = m.get("operations")
    reqs = list(ops.values()) if isinstance(ops, dict) and ops else [m.get("request")]
    if isinstance(ops, dict) and (len(ops) > 20 or not all(re.fullmatch(r"\w{1,40}", k) for k in ops)):
        raise ValueError("operations: max 20, names must be letters/digits/_")
    base = str(m.get("base", ""))
    if base and not _URL.match(base):
        raise ValueError("base must start with http(s):// and have a fixed host")
    for r in reqs:
        if not isinstance(r, dict) or str(r.get("method", "GET")).upper() not in METHODS:
            raise ValueError("every request needs method GET/POST/PUT/PATCH/DELETE")
        u = str(r.get("url", ""))
        if not (_URL.match(u) or (base and u.startswith("/"))):
            raise ValueError("request url must start with http(s):// and have a fixed host (or start with / when 'base' is set)")
    a = m.get("auth")
    if a and not (isinstance(a, dict) and a.get("type") in ("microsoft", "integration") and a.get("app")):
        raise ValueError('auth must look like {"type": "microsoft"|"integration", "app": "excel"}')
    icon = m.get("icon")
    if icon and (not str(icon).startswith("data:image/") or len(icon) > 300_000):
        raise ValueError("icon must be a data:image/... URL up to ~200 KB")
    return m


def _sub(v, d: dict, enc: dict | None = None):
    """enc=None: plain substitution. enc={key: safe_chars}: percent-encode values (used for URLs)."""
    if isinstance(v, str):
        if enc is not None:
            return _VAR.sub(lambda x: quote(str(d.get(x.group(1), "")), safe=enc.get(x.group(1), "")), v)
        full = _VAR.fullmatch(v)
        if full:
            return d.get(full.group(1), "")
        return _VAR.sub(lambda x: str(d.get(x.group(1), "")), v)
    if isinstance(v, dict):
        return {(_sub(k, d) if enc is None and isinstance(k, str) and "${" in k else k): _sub(x, d, enc) for k, x in v.items()}
    if isinstance(v, list):
        return [_sub(x, d, enc) for x in v]
    return v


def _pick(body, path: str):
    cur = body
    for p in str(path).split("."):
        if isinstance(cur, list) and p.isdigit():
            cur = cur[int(p)] if int(p) < len(cur) else None
        elif isinstance(cur, dict):
            cur = cur.get(p)
        else:
            return None
    return cur


async def _auth(db, m: dict, data: dict, ctx: dict) -> dict:
    """Resolve the user's saved connection -> {public settings..., token}. Ownership is enforced."""
    a = m.get("auth")
    if not a:
        return {}
    from app.core.crypto import decrypt_json
    from app.models.app_integration import AppIntegration
    from app.services.integration_tester import _ms_token
    cid, uid = data.get("connectionId"), ctx.get("__user_id__")
    if not cid:
        raise RuntimeError(f"Select a {a['app']} connection in the node")
    try:
        row = await db.get(AppIntegration, UUID(str(cid)))
    except ValueError:
        raise RuntimeError("Invalid connection id")
    if not row or row.app != a["app"] or str(row.user_id) != str(uid):
        raise RuntimeError(f"{a['app']} connection not found")
    if row.is_active is False:
        raise RuntimeError("Connection is disabled")
    cfg, sec = row.config or {}, decrypt_json(row.secrets_encrypted) or {}
    if a["type"] == "integration":                 # e.g. Notion: secrets (apiKey...) usable as ${apiKey}
        return {**cfg, **sec}
    try:
        token = await _ms_token({**cfg, **sec})
    except ValueError as e:
        raise RuntimeError(f"Microsoft login failed: {e}")
    return {**cfg, "token": token}


async def package_allowed(db, pkg, user_id: str) -> bool:
    from app.models.package import PackageUser
    if not pkg or not pkg.is_active:
        return False
    if pkg.access == "all":
        return True
    return bool(await db.scalar(select(PackageUser.user_id).where(
        PackageUser.package_id == pkg.id, PackageUser.user_id == str(user_id))))


def build_request(m: dict, data: dict, extra: dict):
    """Pick the operation, merge manifest defaults, substitute ${fields}. Returns (op, request, resolved, httpx kwargs)."""
    ops = m.get("operations")
    if ops:
        op = data.get("operation") or next(iter(ops))
        if op not in ops:
            raise RuntimeError(f"Unknown operation '{op}'")
        r = dict(ops[op])
    else:
        op, r = None, dict(m["request"])
    d = m.get("defaults") or {}
    r["headers"] = {**(d.get("headers") or {}), **(r.get("headers") or {})}
    if str(r["url"]).startswith("/"):
        r["url"] = m["base"].rstrip("/") + r["url"]
    vals = {}
    for f in m.get("fields", []):
        v = data.get(f["key"], f.get("default", ""))
        if f.get("json") and isinstance(v, str) and v.strip():
            try:
                v = json.loads(v)
            except json.JSONDecodeError:
                raise RuntimeError(f"Field '{f.get('label', f['key'])}' is not valid JSON")
        elif f.get("id") and isinstance(v, str) and v.strip():       # accept a pasted link: keep only the ID
            found = _UUID.findall(v)
            v = found[-1] if found else v.strip()
        elif f.get("type") == "number" and isinstance(v, str) and v.strip():
            try:
                v = float(v) if "." in v else int(v)
            except ValueError:
                pass
        vals[f["key"]] = v
    labels = {f["key"]: f.get("label", f["key"]) for f in m.get("fields", [])}
    for k in _VAR.findall(str(r["url"])):                       # required: anything used in the URL path
        if k in labels and vals.get(k) in ("", None):
            raise RuntimeError(f"'{labels[k]}' is required for {op or 'this node'}")
    vals = {**extra, **vals, **({"token": extra["token"]} if "token" in extra else {})}   # token can't be overridden
    safe = {f["key"]: "/" for f in m.get("fields", []) if f.get("path")}
    req = _sub(r, vals)
    req["url"] = _sub(r["url"], vals, safe)
    headers = {k: str(v) for k, v in (req.get("headers") or {}).items() if str(v).strip()}
    body, params = req.get("body"), req.get("query") or None
    if r.get("dropEmpty"):                         # optional values left blank are not sent
        if isinstance(body, dict):
            body = {k: v for k, v in body.items() if v not in ("", None)}
        if isinstance(params, dict):
            params = {k: v for k, v in params.items() if v not in ("", None)}
    kw = {"headers": headers, "params": params or None}
    if isinstance(body, (dict, list)):
        kw["json"] = body
    elif body not in (None, ""):
        kw["content"] = str(body)
    return op, r, req, kw


async def run_package(ntype: str, data: dict, ctx: dict, sn):
    from app.database.db import AsyncSessionLocal
    from app.models.package import Package
    try:
        pid = UUID(ntype.split("_", 1)[1])
    except Exception:
        raise RuntimeError(f"Invalid package node: {ntype}")
    async with AsyncSessionLocal() as db:
        pkg = await db.get(Package, pid)
        if not await package_allowed(db, pkg, ctx.get("__user_id__", "")):
            raise RuntimeError("This package is disabled or not assigned to you")
        m = pkg.manifest
        extra = await _auth(db, m, data, ctx)
    op, r, req, kw = build_request(m, data, extra)
    async with httpx.AsyncClient(timeout=float(r.get("timeout", 30))) as c:
        resp = await c.request(str(req.get("method", "GET")).upper(), req["url"], **kw)
    try:
        out = resp.json()
    except (json.JSONDecodeError, ValueError):
        out = resp.text[:100_000]
    if resp.status_code >= 400 and r.get("failOnError", True):
        e = out.get("error") if isinstance(out, dict) else None
        msg = (e.get("message") if isinstance(e, dict) else None) or (out.get("message") if isinstance(out, dict) else None) or str(out)
        msg = str(msg)
        raise RuntimeError(f"{pkg.name}{' / ' + op if op else ''} failed: HTTP {resp.status_code} {msg[:200]} | called: {req.get('method', 'GET')} {req['url'][:200]}")
    result = {"status": resp.status_code, "body": out}
    for name, path in (r.get("pick") or {}).items():
        result[name] = _pick(out, path)
    var = data.get("outputVar") or r.get("output") or m.get("output") or f"pkg.{pkg.name.lower().replace(' ', '_')}"
    return sn(ctx, var, result), f"📦 {pkg.name}{' / ' + op if op else ''} -> {var} ({resp.status_code})", None