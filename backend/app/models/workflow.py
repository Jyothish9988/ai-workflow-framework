from uuid import uuid4
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import String, ForeignKey, DateTime, Enum as SqlEnum, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.db import Base


# Always timezone-aware UTC
def utcnow():
    return datetime.now(timezone.utc)


class WorkflowStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class Workflow(Base):
    __tablename__ = "awf_workflows"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )

    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("awf_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    description: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True
    )

    status: Mapped[WorkflowStatus] = mapped_column(
        SqlEnum(WorkflowStatus),
        default=WorkflowStatus.DRAFT,
        nullable=False
    )

    workflow_json: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False
    )

    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False
    )

    # One workflow can have multiple schedules
    schedules = relationship(
        "ScheduledWorkflow",
        back_populates="workflow",
        lazy="selectin",
        cascade="all, delete-orphan"
    )