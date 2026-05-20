"""User model — one row per team member.

Soft-deleted (30-day window per spec §10). Locale is per-user so invitation
and notification copy can be Dutch or English.

Auth model: a row is considered **active** iff:
    password_hash IS NOT NULL  AND  accepted_at IS NOT NULL  AND  deleted_at IS NULL

A CEO-invited user starts with `invited_at` set, `accepted_at` and
`password_hash` null. The frontend `/accept-invite` flow consumes the
invitation token and writes both fields.

`must_change_password` is True for the seeded CEO (forced rotation off the
shared env-provided password) and False once the user has chosen their own.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import Role, pg_enum


class UserModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(320), unique=True, index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[Role] = mapped_column(pg_enum(Role, name="role"), nullable=False)
    locale: Mapped[str] = mapped_column(String(8), default="nl", nullable=False)

    # --- Auth ---
    # Nullable: users invited-but-not-yet-accepted have no hash on file.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # --- Invitation lifecycle ---
    invited_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    invited_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # --- Auditing ---
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


__all__ = ["UserModel"]
