"""Business model — a top-level tenant.

Atlas hosts multiple businesses owned by a single CEO super-admin. Every
business-scoped row in the DB carries a `business_id` FK and is filtered by
Postgres RLS at query time. Soft-deleted with a 30-day window (spec §10).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class BusinessModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "businesses"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    # GCS object key for the business logo, e.g.
    # `businesses/<business_id>/logo-<uuid>.png`. Signed read URLs are
    # minted on response — never stored.
    logo_object_name: Mapped[str | None] = mapped_column(
        String(512), nullable=True
    )


__all__ = ["BusinessModel"]
