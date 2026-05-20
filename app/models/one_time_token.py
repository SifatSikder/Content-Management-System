"""One-time tokens — backs invitations and password resets.

The raw token is never persisted: only its SHA-256 hex digest. The raw value
travels in the email link and is verified by hashing the incoming value and
looking it up.

A user can have multiple outstanding tokens (e.g. an unconsumed invitation
plus a fresh password-reset request) — uniqueness is on `token_hash`, not on
`(user_id, purpose)`. When a token of the same purpose is re-issued (resend
invite, repeated forgot-password), the caller deletes the prior unconsumed
row in the same transaction.

TTLs:
    invitation     → 7 days  (Settings.invitation_ttl_seconds)
    password_reset → 1 hour  (Settings.password_reset_ttl_seconds)
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import TokenPurpose, pg_enum


class OneTimeTokenModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "one_time_tokens"

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
    purpose: Mapped[TokenPurpose] = mapped_column(
        pg_enum(TokenPurpose, name="token_purpose"),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


__all__ = ["OneTimeTokenModel"]
