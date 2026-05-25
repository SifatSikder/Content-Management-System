"""Per-(user, department, event_key) notification opt-in/out.

Replaces the wide `user_notification_prefs.push_*` column set. A row here
overrides the department event's `default_enabled` bit; absence means
"inherit the default".

Why a child table rather than a JSONB blob:
  * cheap to query "what events did user X mute" without parsing JSON
  * cheap to audit changes (each row carries timestamps)
  * cheap to filter by department for the settings UI grouping
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class UserNotificationPrefEventModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_notification_pref_events"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "department_id",
            "event_key",
            name="uq_user_pref_event",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_key: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)


__all__ = ["UserNotificationPrefEventModel"]
