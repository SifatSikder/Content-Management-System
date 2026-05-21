"""Per-user external-OAuth credentials (Phase 3).

Currently used only for Google Drive (`provider="google_drive"`). Refresh
tokens are encrypted at rest with Fernet (`app.core.crypto`). One row per
(user, provider) — reconnecting overwrites the existing row.

Why not stash this on `users`: Google access is opt-in per team member, the
scopes evolve independently of the user record, and we want a clean revoke
path that doesn't touch the user row.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ConnectedGoogleAccountModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "connected_google_accounts"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_connected_google_user_provider"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Free-form string so we can layer in Sheets / Calendar later without an
    # enum migration. Today: only "google_drive".
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    # The Google account email the user connected (for display in /settings).
    google_email: Mapped[str] = mapped_column(String(320), nullable=False)
    # Fernet ciphertext of the refresh token. Never log this column.
    encrypted_refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    # Space-separated scope list granted at consent time.
    scopes: Mapped[str] = mapped_column(Text, nullable=False)
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


__all__ = ["ConnectedGoogleAccountModel"]
