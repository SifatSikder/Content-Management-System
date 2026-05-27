"""Shoot model — one row per scheduled shoot day on a project."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ShootStatus, pg_enum


class ShootModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "shoots"

    business_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # GCS object name for the uploaded call-sheet PDF.
    call_sheet_object_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[ShootStatus] = mapped_column(
        pg_enum(ShootStatus, name="shoot_status"),
        nullable=False,
        default=ShootStatus.SCHEDULED,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    wrapped_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


__all__ = ["ShootModel"]
