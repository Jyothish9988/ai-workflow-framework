from uuid import uuid4
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Text, Float, Integer, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.database.db import Base


def utcnow():
    return datetime.now(timezone.utc)


class ExecutionStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    CANCELLED = "cancelled" 


class NodeStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled" 


class WorkflowExecution(Base):
    __tablename__ = "awf_workflow_executions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("awf_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    user = relationship("User", backref="executions")

    workflow_id: Mapped[str] = mapped_column(String, nullable=False, index=True)

    status: Mapped[str] = mapped_column(
        SAEnum(ExecutionStatus),
        default=ExecutionStatus.PENDING
    )

    trigger_type: Mapped[str] = mapped_column(String(64), default="manual")

    initial_context: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB), nullable=True)
    final_context: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB), nullable=True)

    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    error_traceback: Mapped[str] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    duration_ms: Mapped[float] = mapped_column(Float, nullable=True)

    nodes_total: Mapped[int] = mapped_column(Integer, default=0)
    nodes_success: Mapped[int] = mapped_column(Integer, default=0)
    nodes_failed: Mapped[int] = mapped_column(Integer, default=0)
    nodes_skipped: Mapped[int] = mapped_column(Integer, default=0)

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

    node_logs = relationship(
        "NodeExecutionLog",
        back_populates="execution",
        cascade="all, delete-orphan",
        order_by="NodeExecutionLog.sequence"
    )


class NodeExecutionLog(Base):
    __tablename__ = "awf_node_execution_logs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    execution_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("awf_workflow_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    node_id: Mapped[str] = mapped_column(String(128), nullable=False)
    node_type: Mapped[str] = mapped_column(String(64), nullable=False)
    node_label: Mapped[str] = mapped_column(String(256), nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[str] = mapped_column(SAEnum(NodeStatus), default=NodeStatus.PENDING)

    log_message: Mapped[str] = mapped_column(Text, nullable=True)

    input_context: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB), nullable=True)
    output_context: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB), nullable=True)
    context_diff: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB), nullable=True)

    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    error_traceback: Mapped[str] = mapped_column(Text, nullable=True)

    branch_taken: Mapped[str] = mapped_column(String(64), nullable=True)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    duration_ms: Mapped[float] = mapped_column(Float, nullable=True)

    execution = relationship("WorkflowExecution", back_populates="node_logs")