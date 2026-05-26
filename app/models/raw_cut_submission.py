"""Raw-cut submissions uploaded by the director at the end of `shoot_done`.

Multiple rows per project are allowed (one per file). The first row inserted
auto-advances the project from `shoot_done` to `editing`, so the editor can
pick the cuts up and start the cut. Editor's polished cuts live on
`edit_versions` (`app/models/edit.py`) — raw_cut_submissions are strictly
director-uploaded source material, not reviewable cuts.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.user import UserModel


class RawCutSubmissionModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "raw_cut_submissions"

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
    uploader_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    gcs_bucket: Mapped[str] = mapped_column(String(128), nullable=False)
    gcs_object_name: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    byte_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    uploader: Mapped[UserModel] = relationship(
        UserModel, foreign_keys=[uploader_id], lazy="raise"
    )


__all__ = ["RawCutSubmissionModel"]
