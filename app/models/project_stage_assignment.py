"""Per-stage assignment of users to projects.

A project carries one or more *active* assignees per stage. The active set is
recomputed whenever the project's stage changes — entering a new stage seeds
default assignees per the department's stage-handoff rules (Phase 4); the
Asst CEO can then add/remove people from the card itself.

Rows are history-preserving: removing an assignee sets `removed_at` instead
of deleting the row, so we keep an audit trail of "who was on this card at
which point". Active assignees are `removed_at IS NULL`.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.user import UserModel


class ProjectStageAssignmentModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "project_stage_assignments"
    __table_args__ = (
        # Fast lookup of "who's active on this card right now": filter by
        # project_id + stage_key, then by removed_at IS NULL.
        Index(
            "ix_project_stage_assignments_project_stage_active",
            "project_id",
            "stage_key",
            "removed_at",
        ),
    )

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
    stage_key: Mapped[str] = mapped_column(String(120), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    removed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    user: Mapped[UserModel] = relationship(
        UserModel, foreign_keys=[user_id], lazy="raise"
    )


__all__ = ["ProjectStageAssignmentModel"]
