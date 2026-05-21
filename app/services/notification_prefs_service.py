"""User notification preferences (Phase 3 Task 3.5).

Lazy-creates a `user_notification_prefs` row on first read. `is_event_enabled`
is the predicate `push_service.notify_user` calls before enqueuing a job.
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification_prefs import EVENT_FIELDS, UserNotificationPrefsModel

log = structlog.get_logger(__name__)


async def get_or_create(
    session: AsyncSession, *, user_id: uuid.UUID
) -> UserNotificationPrefsModel:
    """Return the user's prefs row, creating one with defaults if absent."""
    result = await session.execute(
        select(UserNotificationPrefsModel).where(
            UserNotificationPrefsModel.user_id == user_id
        )
    )
    row = result.scalar_one_or_none()
    if row is not None:
        return row
    row = UserNotificationPrefsModel(user_id=user_id)
    session.add(row)
    await session.flush()
    return row


async def update_prefs(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    patch: dict[str, bool],
) -> UserNotificationPrefsModel:
    """Patch any subset of event flags.

    Accepts either the short event key (e.g. `cut_uploaded`) or the column
    name (`push_cut_uploaded`). Unknown keys are ignored.
    """
    row = await get_or_create(session, user_id=user_id)
    valid_columns = set(EVENT_FIELDS.values())
    for key, enabled in patch.items():
        field = EVENT_FIELDS.get(key) or (key if key in valid_columns else None)
        if field is None:
            continue
        setattr(row, field, bool(enabled))
    return row


async def is_event_enabled(
    session: AsyncSession, *, user_id: uuid.UUID, event_key: str
) -> bool:
    """Return True if the user wants to receive `event_key`.

    Unknown events default to **True** — fail-open so a new event we forget
    to wire into the prefs schema still reaches the user.
    """
    field = EVENT_FIELDS.get(event_key)
    if field is None:
        return True
    result = await session.execute(
        select(UserNotificationPrefsModel).where(
            UserNotificationPrefsModel.user_id == user_id
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        return True  # Defaults are all on.
    return bool(getattr(row, field))


__all__ = ["get_or_create", "is_event_enabled", "update_prefs"]
