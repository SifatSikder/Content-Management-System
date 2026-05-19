"""Script + version + comment models.

One `ScriptModel` per project (1:1). Each version is immutable once written —
"editing the script" means creating a new version. Comments hang off a version,
not the script as a whole, so the threaded discussion is preserved across
revisions even after a version is locked.
"""

from __future__ import annotations

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


class ScriptModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One row per project — holds metadata about the script as a whole."""

    __tablename__ = "scripts"

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


__all__ = ["ScriptCommentModel", "ScriptModel", "ScriptVersionModel"]
