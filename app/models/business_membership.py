"""Business membership — links a user to a business with lifecycle state.

The CEO super-admin bypasses these rows entirely (RLS short-circuits when
`app.is_super_admin = true`). Every non-CEO user must have an `active`
membership row in a business to see any of its data.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import BusinessMembershipStatus, pg_enum


class BusinessMembershipModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "business_memberships"
    __table_args__ = (
        UniqueConstraint("business_id", "user_id", name="uq_business_membership_user"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[BusinessMembershipStatus] = mapped_column(
        pg_enum(BusinessMembershipStatus, name="business_membership_status"),
        nullable=False,
        default=BusinessMembershipStatus.INVITED,
    )
    invited_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    joined_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


__all__ = ["BusinessMembershipModel"]
