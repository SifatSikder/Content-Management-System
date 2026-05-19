"""Magic-link token model — short-lived, single-use.

Stored hashed (we never persist the raw token). Created by `auth_service.request_link`
and consumed exactly once by `auth_service.verify`. The 15-minute TTL is in
`Settings.magic_link_ttl_seconds`.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MagicLinkModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "magic_links"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # SHA-256 hex digest of the raw token; raw is sent in the email link only.
    token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


__all__ = ["MagicLinkModel"]
