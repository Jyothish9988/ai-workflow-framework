import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.app_integration_catalog import CATALOG


def _check_app(v: str) -> str:
    if v not in CATALOG:
        raise ValueError(f"Unsupported app '{v}'")
    return v


class IntegrationCreate(BaseModel):
    app: str
    name: str = Field(min_length=1, max_length=120)
    # Mixed public + secret values, exactly as the form sends them.
    config: dict[str, str] = Field(default_factory=dict)

    _v_app = field_validator("app")(_check_app)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name cannot be empty")
        return v


class IntegrationUpdate(BaseModel):
    app: str | None = None  # accepted (the form sends it) but cannot be changed
    name: str | None = Field(default=None, min_length=1, max_length=120)
    # Secret keys that are missing/blank keep their stored value.
    config: dict[str, str] | None = None


class IntegrationTestDraft(IntegrationCreate):
    """Test credentials before saving. When editing, pass `id` so stored secrets are merged in."""
    id: uuid.UUID | None = None


class IntegrationOut(BaseModel):
    """Never contains secret values. JSON keys are camelCase to match the React page."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    app: str
    name: str
    config: dict[str, str]
    configured_secrets: list[str] = Field(default_factory=list, serialization_alias="configuredSecrets")
    status: str
    last_checked: datetime | None = Field(default=None, serialization_alias="lastChecked")
    last_error: str | None = Field(default=None, serialization_alias="lastError")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class TestResult(BaseModel):
    ok: bool
    message: str