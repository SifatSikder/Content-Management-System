"""Draft Idea — one row per project, many versions, many signoffs per version.

Mirrors the shape of `app/models/script.py`. The Asst CEO authors each
version; the active assignees on the `draft_idea` stage sign off with
`looks_good` / `needs_changes`. Locking the idea (per-project property
`locked_at` / `locked_by`) advances the project to `script_drafting`.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class IdeaModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One row per project — holds the idea-phase lock state."""

    __tablename__ = "ideas"

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
        unique=True,
    )
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("idea_versions.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    locked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    locked_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )


class IdeaVersionModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An immutable snapshot of the idea. Bumped on every save."""

    __tablename__ = "idea_versions"
    __table_args__ = (
        UniqueConstraint("idea_id", "version_number", name="uq_idea_version_number"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    idea_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ideas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    body_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class SignoffDecision(enum.StrEnum):
    LOOKS_GOOD = "looks_good"
    NEEDS_CHANGES = "needs_changes"


class IdeaSignoffModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One signoff per (version, reviewer). The latest row per
    (version_id, reviewer_id) is authoritative — new signoffs from the
    same reviewer simply add another row, and queries always order by
    `created_at DESC LIMIT 1` per reviewer."""

    __tablename__ = "idea_signoffs"

    business_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    idea_version_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("idea_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reviewer_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    decision: Mapped[SignoffDecision] = mapped_column(
        Enum(SignoffDecision, name="idea_signoff_decision"),
        nullable=False,
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)


__all__ = [
    "IdeaModel",
    "IdeaSignoffModel",
    "IdeaVersionModel",
    "SignoffDecision",
]
