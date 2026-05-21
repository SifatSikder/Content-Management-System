"""Project model — the central entity. Each row is one video production.

Stage progresses through `PipelineStage`. Soft-deleted with 30-day window
(spec §10). `script_locked_at` / `script_locked_by` capture when a director
locked the script (so /unlock is auditable).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import Category, PipelineStage, pg_enum
from app.models.user import UserModel


class ProjectModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    category: Mapped[Category] = mapped_column(
        pg_enum(Category, name="category"), nullable=False
    )
    stage: Mapped[PipelineStage] = mapped_column(
        pg_enum(PipelineStage, name="pipeline_stage"),
        nullable=False,
        default=PipelineStage.IDEA,
        index=True,
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    owner: Mapped[UserModel] = relationship(UserModel, foreign_keys=[owner_id], lazy="selectin")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Script-lock audit
    script_locked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    script_locked_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    # --- Google Drive (Phase 3 Task 3.3) -----------------------------------
    # Drive folder ID + display URL attached to the project. Access uses the
    # *caller's* connected Drive token (per-user OAuth), not a shared service
    # account, so revoking a team member's Drive doesn't break the project.
    drive_folder_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    drive_folder_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)


__all__ = ["ProjectModel"]
