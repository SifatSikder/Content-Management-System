"""Script + version + comment + signoff models.

One `ScriptModel` per project (1:1). Each version is immutable once written —
"editing the script" means creating a new version (mirrors the idea flow).
Comments hang off a version. Signoffs are per-(version, reviewer) and gate
the lock action via `script_service.lock_gate_status`.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import pg_enum


class ScriptModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One row per project — holds metadata about the script as a whole."""

    __tablename__ = "scripts"

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
        ForeignKey("script_versions.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )


class ScriptVersionModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An immutable snapshot of the script. Bumped on every save."""

    __tablename__ = "script_versions"
    __table_args__ = (
        UniqueConstraint("script_id", "version_number", name="uq_script_version_number"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    script_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("scripts.id", ondelete="CASCADE"),
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


class ScriptCommentModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Inline paragraph comment on a script version."""

    __tablename__ = "script_comments"
    __table_args__ = (
        Index("ix_script_comments_version_created", "version_id", "created_at"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("script_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # An optional inline anchor (e.g. a paragraph id from the tiptap editor).
    paragraph_anchor: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )


class ScriptSignoffDecision(enum.StrEnum):
    LOOKS_GOOD = "looks_good"
    NEEDS_CHANGES = "needs_changes"


class ScriptSignoffModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One signoff per (version, reviewer). The latest row per
    (script_version_id, reviewer_id) is authoritative — new signoffs
    from the same reviewer simply add another row, and queries always
    order by `created_at DESC LIMIT 1` per reviewer. Mirrors
    `IdeaSignoffModel`."""

    __tablename__ = "script_signoffs"

    business_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    script_version_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("script_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reviewer_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    decision: Mapped[ScriptSignoffDecision] = mapped_column(
        pg_enum(ScriptSignoffDecision, name="script_signoff_decision"),
        nullable=False,
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)


__all__ = [
    "ScriptCommentModel",
    "ScriptModel",
    "ScriptSignoffDecision",
    "ScriptSignoffModel",
    "ScriptVersionModel",
]
