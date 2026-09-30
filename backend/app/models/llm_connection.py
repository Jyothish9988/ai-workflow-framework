import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, Text
from app.database.db import Base

class LLMConnection(Base):
    __tablename__ = "awf_llm_connections"

    id         = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id    = Column(String, nullable=False, index=True)
    name       = Column(String, nullable=False)
    provider   = Column(String, nullable=False)  # openai, anthropic, groq, ollama
    api_key    = Column(Text, nullable=True)
    base_url   = Column(String, nullable=True)
    model      = Column(String, nullable=False)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))