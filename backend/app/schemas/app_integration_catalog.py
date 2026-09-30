"""
Which config keys exist for each app and which of them are secret.
Keep in sync with the APPS catalog in the React page (AppIntegration.jsx).
Secret keys are encrypted at rest and never returned by the API.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class AppSpec:
    public: frozenset
    secret: frozenset


def spec(public=(), secret=()) -> AppSpec:
    return AppSpec(frozenset(public), frozenset(secret))


def google(extra_public=()) -> AppSpec:
    return spec({"authMode", "clientId", *extra_public}, {"serviceAccountJson", "clientSecret", "refreshToken"})


def microsoft(extra_public=()) -> AppSpec:
    return spec({"tenantId", "clientId", *extra_public}, {"clientSecret"})


CATALOG: dict[str, AppSpec] = {
    # Email
    "smtp": spec({"host", "port", "secure", "username", "from", "imapHost", "imapPort"}, {"password"}),
    "gmail": spec({"authMode", "email", "clientId"}, {"appPassword", "clientSecret", "refreshToken"}),
    "outlook": microsoft({"mailbox"}),
    # Messaging
    "telegram": spec({"chatId"}, {"botToken"}),
    "whatsapp": spec({"phoneNumberId", "businessAccountId", "apiVersion"}, {"accessToken", "verifyToken"}),
    "slack": spec({"channel"}, {"token"}),
    "teams": spec({"authMode", "tenantId", "clientId"}, {"webhookUrl", "clientSecret"}),
    "discord": spec(secret={"webhookUrl"}),
    # Google Workspace
    "gsheets": google({"spreadsheetId"}),
    "gcalendar": google({"calendarId"}),
    "gdrive": google({"folderId"}),
    "gdocs": google(),
    "google_other": google({"scopes"}),
    # Microsoft 365
    "outlook_calendar": microsoft({"mailbox"}),
    "excel": microsoft({"driveUser"}),
    "onedrive": microsoft({"siteId", "driveUser"}),
    # Other
    "github": spec({"owner"}, {"token"}),
    "notion": spec(secret={"apiKey"}),
    "custom": spec({"baseUrl", "headerName"}, {"apiKey"}),
}