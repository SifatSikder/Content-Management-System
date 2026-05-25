"""Project model — the central entity. Each row is one production unit
inside a department's pipeline.

Stage is read via the `stage` relationship to `department_stages`; the
legacy `PipelineStage` enum column was dropped in Phase B. Soft-deleted
with a 30-day window per spec §10.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.department import DepartmentModel
from app.models.department_stage import DepartmentStageModel
from app.models.enums import Category, pg_enum
from app.models.user import UserModel


class ProjectModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    category: Mapped[Category] = mapped_column(
        pg_enum(Category, name="category"), nullable=False
    )

    # --- Multi-business scaffolding (Phase A) → backfilled in Phase B ------
    business_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    stage_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("department_stages.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Eager-loaded so `project.stage.key` is always available without an
    # extra round-trip. Every project page reads it; lazy would just punt
    # one query for every project to a follow-up SELECT.
    stage: Mapped[DepartmentStageModel] = relationship(
        DepartmentStageModel, foreign_keys=[stage_id], lazy="selectin"
    )
    department: Mapped[DepartmentModel] = relationship(
        DepartmentModel, foreign_keys=[department_id], lazy="selectin"
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
