"""Edit version + comment models.

An `EditVersionModel` is one uploaded cut (V1, V2, …). The video bytes live in
GCS; we store the bucket + object name + content type + size. Comments are
timestamped against the video timeline.

`resolved_comments` is a JSONB array of comment-ids the uploader claims to have
addressed in this version — surfaced as a checklist in the V2 upload UI.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import EditStatus, pg_enum


class EditVersionModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "edit_versions"
    __table_args__ = (
        UniqueConstraint("project_id", "version_number", name="uq_edit_version_number"),
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
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    uploader_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    gcs_bucket: Mapped[str] = mapped_column(String(128), nullable=False)
    gcs_object_name: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)

    status: Mapped[EditStatus] = mapped_column(
        pg_enum(EditStatus, name="edit_status"),
        nullable=False,
        default=EditStatus.IN_REVIEW,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # List of EditCommentModel ids the uploader resolved when creating this version.
    resolved_comments: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )


class EditCommentModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "edit_comments"
    __table_args__ = (
        Index("ix_edit_comments_version_created", "edit_version_id", "created_at"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    edit_version_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("edit_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    timestamp_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # `sent_at IS NULL` = draft, visible only to the author. Reviewers
    # collect comments locally and dispatch them as a batch by clicking
    # "Send issues to editor" — `dispatch_comments` stamps this column.
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )


class EditApprovalModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One row per (edit_version, reviewer) approval. A version is
    fully approved when every required reviewer has a row pointing at
    it. Mirrors `IdeaSignoffModel` shape but stripped to a simple
    "approved" semantic — there's no needs_changes here; reviewers use
    `request_changes` instead, which is a single per-version action.
    """

    __tablename__ = "edit_approvals"
    __table_args__ = (
        UniqueConstraint(
            "edit_version_id", "reviewer_id", name="uq_edit_approval_reviewer"
        ),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    edit_version_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("edit_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reviewer_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)


__all__ = ["EditApprovalModel", "EditCommentModel", "EditVersionModel"]
