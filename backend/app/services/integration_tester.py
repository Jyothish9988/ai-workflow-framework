"""
Live connection checks for each app. `run_test(app, config)` never raises:
it returns (ok, message). `config` is the merged public + decrypted secret values.
"""
import asyncio
import ipaddress
import json
import re
import smtplib
import socket
import ssl
from urllib.parse import urlparse

import httpx

TIMEOUT = 10


# ---------------------------------------------------------------- helpers
def _need(c: dict, *keys: str) -> None:
    missing = [k for k in keys if not str(c.get(k, "")).strip()]
    if missing:
        raise ValueError(f"Missing required field(s): {', '.join(missing)}")


async def _assert_public_host(host: str) -> None:
    """Block requests to localhost / private networks (SSRF protection)."""
    def _resolve():
        return socket.getaddrinfo(host, None)
    try:
        infos = await asyncio.to_thread(_resolve)
    except socket.gaierror:
        raise ValueError(f"Cannot resolve host '{host}'")
    for info in infos:
        if not ipaddress.ip_address(info[4][0]).is_global:
            raise ValueError("Host resolves to a private or reserved address, which is not allowed")


async def _assert_public_url(url: str, https_only: bool = False) -> str:
    p = urlparse(url)
    allowed = ("https",) if https_only else ("http", "https")
    if p.scheme not in allowed or not p.hostname:
        raise ValueError(f"URL must start with {' or '.join(s + '://' for s in allowed)}")
    await _assert_public_host(p.hostname)
    return url


def _client() -> httpx.AsyncClient:
    # no redirects: a public URL must not be able to bounce us to an internal one
    return httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False)


# ---------------------------------------------------------------- email
def _smtp_login(host: str, port: int, secure: str, user: str, password: str) -> None:
    ctx = ssl.create_default_context()
    smtp = smtplib.SMTP_SSL(host, port, timeout=TIMEOUT, context=ctx) if secure == "ssl" \
        else smtplib.SMTP(host, port, timeout=TIMEOUT)
    with smtp:
        smtp.ehlo()
        if secure == "starttls":
            smtp.starttls(context=ctx)
            smtp.ehlo()
        smtp.login(user, password)


async def t_smtp(c: dict) -> str:
    _need(c, "host", "port", "username", "password")
    await _assert_public_host(c["host"])
    await asyncio.to_thread(
        _smtp_login, c["host"], int(c["port"]), c.get("secure", "starttls"), c["username"], c["password"]
    )
    return "SMTP login successful"


async def t_gmail(c: dict) -> str:
    if c.get("authMode", "app_password") == "oauth":
        await _google_oauth_refresh(c)
        return "Gmail OAuth token refreshed"
    _need(c, "email", "appPassword")
    await asyncio.to_thread(_smtp_login, "smtp.gmail.com", 587, "starttls", c["email"], c["appPassword"])
    return "Gmail login successful"


# ---------------------------------------------------------------- google
GOOGLE_SCOPES = {
    "gsheets": ["https://www.googleapis.com/auth/spreadsheets"],
    "gcalendar": ["https://www.googleapis.com/auth/calendar"],
    "gdrive": ["https://www.googleapis.com/auth/drive"],
    "gdocs": ["https://www.googleapis.com/auth/documents"],
}


async def _google_oauth_refresh(c: dict) -> str:
    _need(c, "clientId", "clientSecret", "refreshToken")
    async with _client() as http:
        r = await http.post("https://oauth2.googleapis.com/token", data={
            "client_id": c["clientId"], "client_secret": c["clientSecret"],
            "refresh_token": c["refreshToken"], "grant_type": "refresh_token",
        })
    data = r.json()
    if r.status_code != 200:
        raise ValueError(data.get("error_description") or data.get("error") or "Google rejected the OAuth credentials")
    return data["access_token"]


def _service_account_refresh(info: dict, scopes: list[str]) -> None:
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account
    creds = service_account.Credentials.from_service_account_info(info, scopes=scopes)
    creds.refresh(Request())


def make_google_tester(app: str):
    async def _t(c: dict) -> str:
        if c.get("authMode", "service_account") == "oauth":
            await _google_oauth_refresh(c)
            return "Google OAuth token refreshed"
        _need(c, "serviceAccountJson")
        try:
            info = json.loads(c["serviceAccountJson"])
        except json.JSONDecodeError:
            raise ValueError("Service account JSON is not valid JSON")
        scopes = GOOGLE_SCOPES.get(app) or [s.strip() for s in c.get("scopes", "").splitlines() if s.strip()]
        if not scopes:
            raise ValueError("Add at least one scope")
        await asyncio.to_thread(_service_account_refresh, info, scopes)
        return f"Service account authenticated ({info.get('client_email', 'unknown')})"
    return _t


# ---------------------------------------------------------------- microsoft
async def _ms_token(c: dict) -> str:
    _need(c, "tenantId", "clientId", "clientSecret")
    if not re.fullmatch(r"[A-Za-z0-9.\-]+", c["tenantId"]):
        raise ValueError("Tenant ID contains invalid characters")
    async with _client() as http:
        r = await http.post(
            f"https://login.microsoftonline.com/{c['tenantId']}/oauth2/v2.0/token",
            data={"client_id": c["clientId"], "client_secret": c["clientSecret"],
                  "scope": "https://graph.microsoft.com/.default", "grant_type": "client_credentials"},
        )
    data = r.json()
    if r.status_code != 200:
        raise ValueError((data.get("error_description") or "Microsoft rejected the credentials").splitlines()[0])
    return data["access_token"]


async def t_microsoft(c: dict) -> str:
    await _ms_token(c)
    return "Microsoft Graph token acquired"


async def t_teams(c: dict) -> str:
    if c.get("authMode", "webhook") == "graph":
        return await t_microsoft(c)
    _need(c, "webhookUrl")
    await _assert_public_url(c["webhookUrl"], https_only=True)
    return "Webhook URL looks valid (no test message was sent)"


# ---------------------------------------------------------------- messaging
async def t_telegram(c: dict) -> str:
    _need(c, "botToken")
    async with _client() as http:
        r = await http.get(f"https://api.telegram.org/bot{c['botToken']}/getMe")
    data = r.json()
    if not data.get("ok"):
        raise ValueError(data.get("description", "Telegram rejected the bot token"))
    return f"Bot @{data['result'].get('username')} verified"


async def t_whatsapp(c: dict) -> str:
    _need(c, "accessToken", "phoneNumberId")
    ver = c.get("apiVersion") or "v20.0"
    if not re.fullmatch(r"v\d+\.\d+", ver) or not c["phoneNumberId"].isdigit():
        raise ValueError("Invalid API version or phone number ID")
    async with _client() as http:
        r = await http.get(
            f"https://graph.facebook.com/{ver}/{c['phoneNumberId']}",
            params={"fields": "display_phone_number,verified_name"},
            headers={"Authorization": f"Bearer {c['accessToken']}"},
        )
    data = r.json()
    if r.status_code != 200:
        raise ValueError(data.get("error", {}).get("message", "WhatsApp rejected the credentials"))
    return f"Connected to {data.get('display_phone_number', 'WhatsApp number')}"


async def t_slack(c: dict) -> str:
    _need(c, "token")
    async with _client() as http:
        r = await http.post("https://slack.com/api/auth.test", headers={"Authorization": f"Bearer {c['token']}"})
    data = r.json()
    if not data.get("ok"):
        raise ValueError(f"Slack error: {data.get('error', 'unknown')}")
    return f"Connected to workspace {data.get('team')} as {data.get('user')}"


async def t_discord(c: dict) -> str:
    _need(c, "webhookUrl")
    p = urlparse(c["webhookUrl"])
    if p.scheme != "https" or p.hostname not in ("discord.com", "discordapp.com") or not p.path.startswith("/api/webhooks/"):
        raise ValueError("Not a valid Discord webhook URL")
    async with _client() as http:
        r = await http.get(c["webhookUrl"])
    if r.status_code != 200:
        raise ValueError(f"Discord rejected the webhook (HTTP {r.status_code})")
    return f"Webhook '{r.json().get('name', '')}' verified"


# ---------------------------------------------------------------- other
async def t_github(c: dict) -> str:
    _need(c, "token")
    async with _client() as http:
        r = await http.get("https://api.github.com/user", headers={
            "Authorization": f"Bearer {c['token']}", "Accept": "application/vnd.github+json"})
    if r.status_code != 200:
        raise ValueError(r.json().get("message", f"GitHub returned HTTP {r.status_code}"))
    return f"Authenticated as {r.json().get('login')}"


async def t_notion(c: dict) -> str:
    _need(c, "apiKey")
    async with _client() as http:
        r = await http.get("https://api.notion.com/v1/users/me", headers={
            "Authorization": f"Bearer {c['apiKey']}", "Notion-Version": "2022-06-28"})
    if r.status_code != 200:
        raise ValueError(r.json().get("message", f"Notion returned HTTP {r.status_code}"))
    return "Notion integration verified"


async def t_custom(c: dict) -> str:
    _need(c, "baseUrl")
    await _assert_public_url(c["baseUrl"])
    headers = {c.get("headerName") or "Authorization": c["apiKey"]} if c.get("apiKey") else {}
    async with _client() as http:
        r = await http.get(c["baseUrl"], headers=headers)
    if r.status_code in (401, 403):
        raise ValueError(f"Server rejected the credentials (HTTP {r.status_code})")
    if r.status_code >= 500:
        raise ValueError(f"Server error (HTTP {r.status_code})")
    return f"Reachable (HTTP {r.status_code})"


HANDLERS = {
    "smtp": t_smtp, "gmail": t_gmail,
    "outlook": t_microsoft, "outlook_calendar": t_microsoft, "excel": t_microsoft, "onedrive": t_microsoft,
    "telegram": t_telegram, "whatsapp": t_whatsapp, "slack": t_slack, "teams": t_teams, "discord": t_discord,
    "gsheets": make_google_tester("gsheets"), "gcalendar": make_google_tester("gcalendar"),
    "gdrive": make_google_tester("gdrive"), "gdocs": make_google_tester("gdocs"),
    "google_other": make_google_tester("google_other"),
    "github": t_github, "notion": t_notion, "custom": t_custom,
}


def _redact(message: str, config: dict) -> str:
    """Never echo secrets back (e.g. Telegram puts the token inside the URL)."""
    for v in config.values():
        if isinstance(v, str) and len(v) >= 6:
            message = message.replace(v, "***")
    return message[:300]


async def run_test(app: str, config: dict) -> tuple[bool, str]:
    handler = HANDLERS.get(app)
    if not handler:
        return False, f"No tester for '{app}'"
    try:
        return True, await handler(config)
    except httpx.TimeoutException:
        return False, "Timed out while contacting the service"
    except smtplib.SMTPAuthenticationError:
        return False, "Authentication failed: check the username and password"
    except Exception as exc:  # noqa: BLE001 - report every failure to the UI
        msg = str(exc) if isinstance(exc, ValueError) else f"{type(exc).__name__}: {exc}"
        return False, _redact(msg, config)