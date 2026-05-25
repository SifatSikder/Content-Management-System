"""Per-user notification preferences (legacy umbrella row).

Phase B moved per-event opt-in/out into `user_notification_pref_events`
(keyed by `user_id` + `department_id` + `event_key`). This umbrella row
stays so existing FK relationships still resolve and so we have a single
spot to attach future cross-department preferences (digest cadence,
quiet hours), but no per-event booleans live here anymore.

For the predicate `push_service.notify_user` calls before enqueuing a
job, see `notification_prefs_service.is_event_enabled`.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class UserNotificationPrefsModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_notification_prefs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )


__all__ = ["UserNotificationPrefsModel"]
