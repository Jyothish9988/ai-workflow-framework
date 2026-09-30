"""Gmail nodes over IMAP/SMTP using an app password.
Credentials come from awf_app_integrations (app='gmail', config.authMode='app_password').
Nodes: gmail_read, gmail_send."""
import asyncio
import imaplib
import json
import mimetypes
import os
import re
import smtplib
import ssl
import uuid
from email import message_from_bytes, policy
from email.message import EmailMessage

from app.core.crypto import decrypt_json
from app.models.app_integration import AppIntegration

FILES_DIR = os.path.realpath(os.getenv("AWF_FILES_DIR", "/tmp/awf_files"))  # attachments live here only
MAX_ATTACH = 25 * 1024 * 1024
MAX_BODY = 20000
MAX_LIMIT = 50
PWD_KEYS = ("appPassword", "app_password", "password", "pass")


def _get(ctx, path):
    cur = ctx
    for p in str(path or "").strip().split("."):
        cur = cur.get(p) if isinstance(cur, dict) else None
    return cur


async def _creds(data, ctx):
    cid, uid, db = data.get("connectionId"), ctx.get("__user_id__"), ctx.get("__db__")
    if not cid:
        raise RuntimeError("Select a Gmail connection in the node")
    if not uid or db is None:
        raise RuntimeError("Missing user context (add __user_id__ in execute_workflow)")
    try:
        row = await db.get(AppIntegration, uuid.UUID(str(cid)))
    except ValueError:
        raise RuntimeError("Invalid Gmail connection id")
    # ownership check: never let one user run another user's connection
    if not row or row.app != "gmail" or str(row.user_id) != str(uid):
        raise RuntimeError("Gmail connection not found")
    if row.is_active is False:
        raise RuntimeError("Gmail connection is disabled")
    cfg = row.config or {}
    if cfg.get("authMode", "app_password") != "app_password":
        raise RuntimeError("Only app-password Gmail connections are supported")
    sec = decrypt_json(row.secrets_encrypted) or {}
    pwd = next((sec[k] for k in PWD_KEYS if sec.get(k)), None) or (next(iter(sec.values()), None) if len(sec) == 1 else None)
    if not cfg.get("email") or not pwd:
        raise RuntimeError("Gmail connection has no email or app password")
    return cfg["email"], str(pwd).replace(" ", "")


def _clean_name(n):
    return re.sub(r"[^\w.\- ]", "_", os.path.basename(n or "file"))[:120] or "file"


def _body_text(msg):
    part = msg.get_body(preferencelist=("plain", "html"))
    if part is None:
        return ""
    try:
        t = part.get_content()
    except Exception:
        return ""
    if part.get_content_type() == "text/html":
        t = re.sub(r"(?s)<(script|style).*?</\1>", "", t)
        t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t)).strip()
    return t[:MAX_BODY]


def _parse(uid, raw, download):
    msg = message_from_bytes(raw, policy=policy.default)
    atts = []
    for part in msg.iter_attachments():
        fn = part.get_filename() or "attachment"
        payload = part.get_payload(decode=True) or b""
        item = {"filename": fn, "mimeType": part.get_content_type(), "size": len(payload)}
        if download and payload and len(payload) <= MAX_ATTACH:
            folder = os.path.join(FILES_DIR, uuid.uuid4().hex)
            os.makedirs(folder, exist_ok=True)
            path = os.path.join(folder, _clean_name(fn))
            with open(path, "wb") as fh:
                fh.write(payload)
            item["path"] = path
        atts.append(item)
    g = lambda h: str(msg[h] or "")
    return {"uid": uid, "message_id": g("message-id"), "from": g("from"), "to": g("to"), "cc": g("cc"),
            "subject": g("subject"), "date": g("date"), "body": _body_text(msg),
            "has_attachments": bool(atts), "attachments": atts}


def _read_sync(user, pwd, a):
    M = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=30)
    out = []
    try:
        M.login(user, pwd)
        typ, _ = M.select(a["folder"], readonly=not a["mark_read"])
        if typ != "OK":
            raise RuntimeError(f"Cannot open folder '{a['folder']}'")
        if a["query"]:
            q = a["query"].replace("\\", "\\\\").replace('"', '\\"')
            typ, d = M.uid("SEARCH", None, "X-GM-RAW", f'"{q}"')
        else:
            typ, d = M.uid("SEARCH", None, "ALL")
        if typ != "OK":
            raise RuntimeError("Gmail search failed")
        uids = (d[0] or b"").split()[-a["limit"]:][::-1]  # newest first
        for u in uids:
            typ, md = M.uid("FETCH", u, "(BODY.PEEK[])")
            if typ == "OK" and md and isinstance(md[0], tuple):
                out.append(_parse(u.decode(), md[0][1], a["download"]))
                if a["mark_read"]:
                    M.uid("STORE", u, "+FLAGS", "(\\Seen)")
    finally:
        try:
            M.logout()
        except Exception:
            pass
    return out


def _addrs(v):
    return [x.strip() for x in re.split(r"[,;]", str(v or "")) if x.strip()]


def _safe_path(p):
    rp = os.path.realpath(str(p))
    if not rp.startswith(FILES_DIR + os.sep) or not os.path.isfile(rp):
        raise RuntimeError(f"Attachment missing or not allowed: {p}")
    return rp


def _send_sync(user, pwd, a):
    to, cc, bcc = _addrs(a["to"]), _addrs(a["cc"]), _addrs(a["bcc"])
    if not to:
        raise RuntimeError("Gmail Send: 'To' is empty")
    if len(to) + len(cc) + len(bcc) > 50:
        raise RuntimeError("Too many recipients (max 50)")
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = user, ", ".join(to), a["subject"]
    if cc:
        msg["Cc"] = ", ".join(cc)
    if bcc:
        msg["Bcc"] = ", ".join(bcc)
    if a["html"]:
        msg.set_content("This email requires an HTML-capable client.")
        msg.add_alternative(a["body"], subtype="html")
    else:
        msg.set_content(a["body"])
    total = 0
    for p in a["paths"]:
        rp = _safe_path(p)
        data = open(rp, "rb").read()
        total += len(data)
        if total > MAX_ATTACH:
            raise RuntimeError("Attachments exceed 25 MB")
        mt, _ = mimetypes.guess_type(rp)
        main, sub = (mt or "application/octet-stream").split("/", 1)
        msg.add_attachment(data, maintype=main, subtype=sub, filename=os.path.basename(rp))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(), timeout=30) as s:
        s.login(user, pwd)
        s.send_message(msg)
    return len(a["paths"])


def _q(v):
    return str(v or "").replace('"', "").strip()


def _build_query(d):
    parts = []
    if _q(d.get("from")):            parts.append(f'from:({_q(d["from"])})')
    if _q(d.get("to")):              parts.append(f'to:({_q(d["to"])})')
    if _q(d.get("subjectContains")): parts.append(f'subject:({_q(d["subjectContains"])})')
    if _q(d.get("bodyContains")):    parts.append(f'"{_q(d["bodyContains"])}"')
    if d.get("newerThan"):           parts.append(f'newer_than:{_q(d["newerThan"])}')
    if d.get("unreadOnly"):          parts.append("is:unread")
    if d.get("hasAttachment"):       parts.append("has:attachment")
    if _q(d.get("extraQuery")):      parts.append(_q(d["extraQuery"]))
    return " ".join(parts)


async def gmail_read(data, ctx, sn):
    user, pwd = await _creds(data, ctx)
    a = {"query": _build_query(data), "folder": data.get("folder") or "INBOX",
         "limit": max(1, min(int(data.get("limit") or 10), MAX_LIMIT)),
         "mark_read": bool(data.get("markRead")), "download": bool(data.get("downloadAttachments"))}
    try:
        msgs = await asyncio.to_thread(_read_sync, user, pwd, a)
    except imaplib.IMAP4.error as e:
        raise RuntimeError(f"Gmail IMAP error (check app password / IMAP enabled): {e}")
    var = data.get("outputVar") or "gmail.messages"
    return sn(ctx, var, msgs), f"Gmail: read {len(msgs)} email(s) -> {var}", None


async def gmail_send(data, ctx, sn):
    user, pwd = await _creds(data, ctx)
    paths = [p for p in (data.get("attachments") or []) if str(p).strip()]
    for item in _get(ctx, data.get("attachmentsVar")) or []:
        p = item.get("path") if isinstance(item, dict) else item
        if p:
            paths.append(p)
    a = {"to": data.get("to"), "cc": data.get("cc"), "bcc": data.get("bcc"), "subject": str(data.get("subject") or ""),
         "body": str(data.get("body") or ""), "html": bool(data.get("html")), "paths": paths}
    try:
        n = await asyncio.to_thread(_send_sync, user, pwd, a)
    except smtplib.SMTPAuthenticationError:
        raise RuntimeError("Gmail rejected the login - check the app password")
    return sn(ctx, "gmail.sent", {"to": a["to"], "subject": a["subject"], "attachments": n}), \
        f"Gmail: sent to {a['to']} ({n} attachment(s))", None


GMAIL_HANDLERS = {"gmail_read": gmail_read, "gmail_send": gmail_send}
