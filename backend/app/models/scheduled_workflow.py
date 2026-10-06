import uuid
from datetime import datetime, timezone as dt_timezone

from sqlalchemy import (
    Column,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database.db import Base


def utcnow():
    return datetime.now(dt_timezone.utc)


class ScheduledWorkflow(Base):
    __tablename__ = "awf_scheduled_workflows"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    user_id = Column(String, nullable=False, index=True)

    workflow_id = Column(
        UUID(as_uuid=True),
        ForeignKey("awf_workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    freq = Column(String, nullable=False, default="manual")
    cron = Column(String, nullable=True)
    time = Column(String, nullable=True)
    day = Column(String, nullable=True)

    # IANA timezone the cron expression is evaluated in (e.g. "Asia/Kolkata")
    timezone = Column(String, nullable=False, default="UTC", server_default="UTC")

    enabled = Column(Boolean, default=False, nullable=False)

    last_run_at = Column(DateTime(timezone=True), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True)

    run_count = Column(Integer, default=0, nullable=False)
    fail_count = Column(Integer, default=0, nullable=False)

    # Most recent execution started by this schedule (scheduled or "Run now")
    last_execution_id = Column(String, nullable=True)
    last_error = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    # Relationship back to Workflow
    workflow = relationship("Workflow", back_populates="schedules", lazy="selectin")