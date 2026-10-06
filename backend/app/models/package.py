from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.db import Base


def utcnow():
    return datetime.now(timezone.utc)


class Package(Base):
    """A declarative node definition (manifest) published by an admin. No code is uploaded or run."""
    __tablename__ = "awf_node_packages"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    icon: Mapped[str | None] = mapped_column(Text, nullable=True)           # optional data: URL
    manifest: Mapped[dict] = mapped_column(JSONB, nullable=False)           # fields + request template
    access: Mapped[str] = mapped_column(String(10), default="all", nullable=False)   # all | assigned
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class PackageUser(Base):
    """Which users may use a package whose access is 'assigned'."""
    __tablename__ = "awf_node_package_users"

    package_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("awf_node_packages.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
