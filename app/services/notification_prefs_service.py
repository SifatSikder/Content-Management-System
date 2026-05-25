"""User notification preferences (Phase B).

Replaces the Phase-3 wide-column model with a per-(user, department, event)
override table. `is_event_enabled` is still the predicate
`push_service.notify_user` calls before enqueuing a job; it now looks up
the user's row in `user_notification_pref_events` first, then falls back
to the department's `department_event_definitions.default_enabled`, then
to True (fail-open) if neither exists.

A `user_notification_prefs` row is still lazy-created on first read — it's
the umbrella per-user record other future cross-department preferences
(digest cadence, quiet hours) will hang off.
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.department_event_definition import DepartmentEventDefinitionModel
from app.models.notification_prefs import UserNotificationPrefsModel
from app.models.user_notification_pref_event import UserNotificationPrefEventModel

log = structlog.get_logger(__name__)


async def get_or_create(
    session: AsyncSession, *, user_id: uuid.UUID
) -> UserNotificationPrefsModel:
    """Return the user's umbrella prefs row, creating one if absent."""
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


async def list_for_department(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    department_id: uuid.UUID,
) -> list[dict[str, object]]:
    """List every event defined in the department, marked with the user's
    effective setting (`enabled = override-or-default`).

    Output rows: `{event_key, name_i18n, default_enabled, enabled}`. Used
    by the settings page to render the per-event toggles.
    """
    defs_q = await session.execute(
        select(DepartmentEventDefinitionModel)
        .where(DepartmentEventDefinitionModel.department_id == department_id)
        .order_by(DepartmentEventDefinitionModel.event_key.asc())
    )
    defs = list(defs_q.scalars().all())
    if not defs:
        return []

    overrides_q = await session.execute(
        select(
            UserNotificationPrefEventModel.event_key,
            UserNotificationPrefEventModel.enabled,
        ).where(
            UserNotificationPrefEventModel.user_id == user_id,
            UserNotificationPrefEventModel.department_id == department_id,
        )
    )
    overrides = {event_key: enabled for event_key, enabled in overrides_q.all()}

    out: list[dict[str, object]] = []
    for d in defs:
        out.append(
            {
                "event_key": d.event_key,
                "name_i18n": d.name_i18n,
                "default_enabled": d.default_enabled,
                "enabled": overrides.get(d.event_key, d.default_enabled),
            }
        )
    return out


async def set_pref(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    department_id: uuid.UUID,
    business_id: uuid.UUID,
    event_key: str,
    enabled: bool,
) -> None:
    """Upsert a `(user, department, event_key)` override."""
    # `enabled` is recorded even when it equals the department default —
    # callers may want to know "this user explicitly opted in" rather than
    # "the default happened to be on". Keeps the audit trail honest.
    stmt = pg_insert(UserNotificationPrefEventModel).values(
        user_id=user_id,
        department_id=department_id,
        business_id=business_id,
        event_key=event_key,
        enabled=enabled,
    ).on_conflict_do_update(
        constraint="uq_user_pref_event",
        set_={"enabled": enabled},
    )
    await session.execute(stmt)


async def is_event_enabled(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    department_id: uuid.UUID,
    event_key: str,
) -> bool:
    """Return True if the user wants to receive `event_key` in this department.

    Lookup order:
      1. user's explicit override row → use that
      2. department's default for the event → use that
      3. no department row at all → fail-open (True)
    """
    override_q = await session.execute(
        select(UserNotificationPrefEventModel.enabled).where(
            UserNotificationPrefEventModel.user_id == user_id,
            UserNotificationPrefEventModel.department_id == department_id,
            UserNotificationPrefEventModel.event_key == event_key,
        )
    )
    override = override_q.scalar_one_or_none()
    if override is not None:
        return bool(override)

    default_q = await session.execute(
        select(DepartmentEventDefinitionModel.default_enabled).where(
            DepartmentEventDefinitionModel.department_id == department_id,
            DepartmentEventDefinitionModel.event_key == event_key,
        )
    )
    default = default_q.scalar_one_or_none()
    if default is not None:
        return bool(default)

    # Fail-open: an event we forgot to define still reaches the user.
    return True


__all__ = [
    "get_or_create",
    "is_event_enabled",
    "list_for_department",
    "set_pref",
]
