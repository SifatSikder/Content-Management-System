"""Per-user notification preferences (Phase 3 Task 3.5).

One row per user. Booleans gate whether push notifications for each event
type are dispatched. Opt-out model — every event defaults to **enabled** so
users see notifications until they explicitly mute them.

The event names mirror `app.services.activity_service` actions but with the
dot replaced by an underscore (Postgres column names can't contain dots).
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey
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

    push_project_created: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    push_script_submitted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    push_script_locked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    push_cut_uploaded: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    push_cut_comment: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    push_cut_approved: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    push_cut_changes_requested: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    push_project_published: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    push_project_stuck: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )


# Event key → model attribute. Keep these in sync.
EVENT_FIELDS: dict[str, str] = {
    "project_created": "push_project_created",
    "script_submitted": "push_script_submitted",
    "script_locked": "push_script_locked",
    "cut_uploaded": "push_cut_uploaded",
    "cut_comment": "push_cut_comment",
    "cut_approved": "push_cut_approved",
    "cut_changes_requested": "push_cut_changes_requested",
    "project_published": "push_project_published",
    "project_stuck": "push_project_stuck",
}


__all__ = ["EVENT_FIELDS", "UserNotificationPrefsModel"]
