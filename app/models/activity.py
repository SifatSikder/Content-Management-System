"""Activity log — append-only audit trail per project.

No `updated_at` and no `deleted_at`: rows are written once and never modified
in-place. Per spec §10, on user deletion the `actor_id` is nulled to redact
PII while leaving the audit row intact.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin
from app.models.user import UserModel


class ActivityModel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "activities"
    __table_args__ = (
        # Primary access pattern: "give me the project's recent activity"
        Index("ix_activities_project_created", "project_id", "created_at"),
    )

    project_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Eager-loaded so the activity feed can render the actor's display name
    # without a follow-up query per row. NULL when the actor was deleted
    # (spec §10 PII redaction).
    actor: Mapped[UserModel | None] = relationship(
        UserModel, foreign_keys=[actor_id], lazy="selectin"
    )
    # Verb-style action key, e.g. "project.created", "script.locked",
    # "edit.uploaded", "edit.approved". Resolved to localised copy in the UI.
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


__all__ = ["ActivityModel"]
