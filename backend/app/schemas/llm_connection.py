# app/schemas/execution.py

from datetime import datetime
from uuid import UUID
from typing import Optional, List, Dict
from pydantic import BaseModel


class LLMConnectionCreate(BaseModel):
    name: str
    provider: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: str
    is_default: bool = False


class LLMConnectionUpdate(BaseModel):
    name: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    is_default: Optional[bool] = None