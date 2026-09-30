from uuid import UUID
from typing import Any
from datetime import datetime
from pydantic import BaseModel
from sqlalchemy.orm import Session

class WorkflowCreate(BaseModel):
    name: str
    description: str | None = None
    workflow_json: dict[str, Any] = {}


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    workflow_json: dict[str, Any] | None = None


class WorkflowResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    description: str | None
    workflow_json: dict[str, Any]
    version: int
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True