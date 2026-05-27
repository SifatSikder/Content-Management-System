"""Per-template default stage-handoff rules.

A handoff says "when a project enters stage X, auto-assign every member
holding one of these roles." The defaults reference role *keys* (the
stable identifier on `department_roles`, not the display name), which
the department-instantiation flow resolves to actual role ids.

Departments where one of the default role keys was deleted by the admin
will skip that role on seed — the handoff still seeds with the
remaining roles, and the admin can edit any time from the Handoffs tab.
"""

from __future__ import annotations

from typing import TypedDict


class StageHandoff(TypedDict):
    stage_key: str
    role_keys: list[str]
    # If False, the auto-assigned occupants cannot be removed from the
    # project card (e.g. the editor on `editing`).
    removable: bool


CONTENT_CREATION_DEFAULT_HANDOFFS: list[StageHandoff] = [
    {"stage_key": "location_scouting", "role_keys": ["assistant_director"]},
    # draft_idea starts with only the Asst CEO assigned. CEO + Director
    # get pulled in on demand via `request_enhancement` when the owner
    # is ready for feedback — they're notified by email at that point.
    {"stage_key": "draft_idea", "role_keys": ["assistant_director"]},
    {"stage_key": "script_drafting", "role_keys": ["assistant_director"]},
    {"stage_key": "casting", "role_keys": ["assistant_director"]},
    # `Lock Casting` advances to `shooting` and auto-assigns the
    # director(s). They get an email at that point — see
    # `cast_service.lock_casting`. Both legacy and renamed role keys
    # are listed so departments running either still wire up correctly.
    {"stage_key": "shooting", "role_keys": ["junior_director", "director"]},
    {"stage_key": "editing", "role_keys": ["editor"]},
    {"stage_key": "edit_review", "role_keys": ["assistant_director", "ceo"]},
    # approved_published is terminal — no handoff.
]


MARKETING_DEFAULT_HANDOFFS: list[StageHandoff] = []


DEFAULT_STAGE_HANDOFFS: dict[str, list[StageHandoff]] = {
    "content_creation": CONTENT_CREATION_DEFAULT_HANDOFFS,
    "marketing": MARKETING_DEFAULT_HANDOFFS,
}


def default_handoffs_for_template(template_key: str | None) -> list[StageHandoff]:
    if not template_key:
        return []
    return DEFAULT_STAGE_HANDOFFS.get(template_key, [])


__all__ = [
    "DEFAULT_STAGE_HANDOFFS",
    "StageHandoff",
    "default_handoffs_for_template",
]
