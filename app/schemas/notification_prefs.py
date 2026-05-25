"""DTOs for /me/notification-prefs (Phase B).

Reflects the new department-scoped shape: events are grouped per
department; each entry carries the user's current effective `enabled`
value (override-or-default) plus the department default so the settings
UI can show "Default: on" / "You overrode this" hints.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class EventPrefPublic(BaseModel):
    event_key: str
    name_i18n: dict[str, str]
    default_enabled: bool
    enabled: bool


class DepartmentPrefsPublic(BaseModel):
    department_id: uuid.UUID
    events: list[EventPrefPublic]


class SetEventPrefBody(BaseModel):
    department_id: uuid.UUID
    event_key: str = Field(min_length=1, max_length=64)
    enabled: bool


__all__ = ["DepartmentPrefsPublic", "EventPrefPublic", "SetEventPrefBody"]
