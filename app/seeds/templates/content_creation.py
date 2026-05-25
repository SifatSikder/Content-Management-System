"""Content Creation — the department template carrying the original Sons Real
Estate real-estate video pipeline (11 stages, 6 roles, 5 capabilities).

Stages, roles, and the role→action permission matrix here are the exact mirror
of what `app/models/enums.py::PipelineStage`/`Role` and
`app/auth/dependencies.py::can_user_move_to_stage`/`_user_can_access_project`
encoded before Phase B. After Phase B lands these stop being the hardcoded
source of truth: they're imported once at migration time, written into
`department_templates`, then copied into `department_stages` +
`department_roles` + `department_role_permissions` when a department is
instantiated from the template.
"""

from __future__ import annotations

from typing import Any

# ---------- stages -------------------------------------------------------
# Order in this list is the order_index assigned when the template is
# instantiated. `allowed_from_stage_keys` is resolved to actual stage ids in
# `app.services.department_service.create_department`.

_STAGES: list[dict[str, Any]] = [
    {
        "key": "idea",
        "name_i18n": {"nl": "Idee", "en": "Idea"},
        "color": "#94a3b8",
        "allowed_from_stage_keys": [],
    },
    {
        "key": "script_drafting",
        "name_i18n": {"nl": "Script schrijven", "en": "Script drafting"},
        "color": "#60a5fa",
        "allowed_from_stage_keys": ["idea"],
    },
    {
        "key": "script_review",
        "name_i18n": {"nl": "Script review", "en": "Script review"},
        "color": "#38bdf8",
        # Submit from drafting, or back from a freshly unlocked locked script.
        "allowed_from_stage_keys": ["script_drafting", "script_locked"],
    },
    {
        "key": "script_locked",
        "name_i18n": {"nl": "Script vergrendeld", "en": "Script locked"},
        "color": "#0ea5e9",
        "allowed_from_stage_keys": ["script_drafting", "script_review"],
    },
    {
        "key": "location_scouting",
        "name_i18n": {"nl": "Locatie scouten", "en": "Location scouting"},
        "color": "#fbbf24",
        # `location_service.create_location` auto-bumps from any pre-shoot
        # stage; manual drag-from-any-script-stage stays valid too.
        "allowed_from_stage_keys": [
            "idea",
            "script_drafting",
            "script_review",
            "script_locked",
        ],
    },
    {
        "key": "casting",
        "name_i18n": {"nl": "Casting", "en": "Casting"},
        "color": "#f59e0b",
        "allowed_from_stage_keys": ["location_scouting"],
    },
    {
        "key": "shoot_scheduled",
        "name_i18n": {"nl": "Opname gepland", "en": "Shoot scheduled"},
        "color": "#fb7185",
        "allowed_from_stage_keys": ["casting"],
    },
    {
        "key": "shoot_done",
        "name_i18n": {"nl": "Opname klaar", "en": "Shoot done"},
        "color": "#f43f5e",
        "allowed_from_stage_keys": ["shoot_scheduled"],
    },
    {
        "key": "editing",
        "name_i18n": {"nl": "Montage", "en": "Editing"},
        "color": "#a78bfa",
        # `edit_service.add_edit_version` auto-bumps from any pre-editing
        # stage; `edit_service.request_changes` bumps back from final_review.
        "allowed_from_stage_keys": ["shoot_done", "final_review"],
    },
    {
        "key": "final_review",
        "name_i18n": {"nl": "Eind review", "en": "Final review"},
        "color": "#8b5cf6",
        "allowed_from_stage_keys": ["editing"],
    },
    {
        "key": "approved_published",
        "name_i18n": {"nl": "Goedgekeurd & gepubliceerd", "en": "Approved & published"},
        "color": "#22c55e",
        "is_terminal": True,
        "allowed_from_stage_keys": ["final_review", "editing"],
    },
]


# ---------- roles --------------------------------------------------------
# At the *department* level "ceo" is just a role name; the global super-admin
# flag still lives on `users.role` (a CEO user implicitly has every department
# permission via the super-admin short-circuit in `permission_service`).

_ROLES: list[dict[str, Any]] = [
    {
        "key": "ceo",
        "name_i18n": {"nl": "CEO", "en": "CEO"},
        "description": "Final approver — can publish, unlock scripts, override any stage move.",
    },
    {
        "key": "assistant_director",
        "name_i18n": {"nl": "Assistent-regisseur", "en": "Assistant Director"},
        "description": "Manages the production pipeline end-to-end (everything except final publish).",
    },
    {
        "key": "junior_director",
        "name_i18n": {"nl": "Junior regisseur", "en": "Junior Director"},
        "description": "Drives projects they own through the pipeline.",
    },
    {
        "key": "editor",
        "name_i18n": {"nl": "Editor", "en": "Editor"},
        "description": "Uploads cuts and addresses revision notes.",
    },
    {
        "key": "crew",
        "name_i18n": {"nl": "Crew", "en": "Crew"},
        "description": "Executes shoots. Read-only access to projects they're assigned to.",
    },
    {
        "key": "viewer",
        "name_i18n": {"nl": "Lezer", "en": "Viewer"},
        "description": "Read-only access across the department.",
    },
]


# ---------- permission matrix --------------------------------------------
# The set of valid stage.move transitions — matches Content Creation's stage
# graph above. `_STAGE_MOVE_ACTION_KEYS` is what the permission service
# expects callers to look up; explicit enumeration keeps the audit trail
# clean.

_STAGE_TRANSITIONS: list[tuple[str, str]] = [
    ("idea", "script_drafting"),
    ("script_drafting", "script_review"),
    ("script_drafting", "script_locked"),
    ("script_review", "script_locked"),
    ("script_locked", "script_review"),
    ("idea", "location_scouting"),
    ("script_drafting", "location_scouting"),
    ("script_review", "location_scouting"),
    ("script_locked", "location_scouting"),
    ("location_scouting", "casting"),
    ("casting", "shoot_scheduled"),
    ("shoot_scheduled", "shoot_done"),
    ("shoot_done", "editing"),
    ("editing", "final_review"),
    ("final_review", "editing"),
    ("final_review", "approved_published"),
    ("editing", "approved_published"),
]


def _stage_move_key(from_key: str, to_key: str) -> str:
    return f"stage.move:{from_key}->{to_key}"


def _build_permissions() -> list[dict[str, Any]]:
    """Translate the role matrix from `app/auth/dependencies.py` into explicit
    `(role_key, action_key, allowed=True)` triples. Anything not listed is
    implicitly denied at lookup time.

    Per-project ownership predicates (e.g. "JD can only mutate projects they
    own") are NOT encoded here — they stay as runtime checks in
    `permission_service`. This list only gates "is this role allowed to
    attempt the action at all".
    """
    rows: list[dict[str, Any]] = []

    publish_actions = {
        _stage_move_key("final_review", "approved_published"),
        _stage_move_key("editing", "approved_published"),
    }

    # --- CEO: everything --------------------------------------------------
    ceo_actions = [
        "project.create",
        "project.edit",
        "project.delete",
        "script_versioning.lock",
        "script_versioning.unlock",
        "asset_review_with_timecodes.approve",
        "asset_review_with_timecodes.request_changes",
    ] + [_stage_move_key(f, t) for f, t in _STAGE_TRANSITIONS]
    for action in ceo_actions:
        rows.append({"role_key": "ceo", "action_key": action, "allowed": True})

    # --- Assistant Director: everything except publish -------------------
    ad_actions = [
        "project.create",
        "project.edit",
        "project.delete",
        "script_versioning.lock",
        "script_versioning.unlock",
        "asset_review_with_timecodes.approve",
        "asset_review_with_timecodes.request_changes",
    ] + [
        _stage_move_key(f, t)
        for f, t in _STAGE_TRANSITIONS
        if _stage_move_key(f, t) not in publish_actions
    ]
    for action in ad_actions:
        rows.append({"role_key": "assistant_director", "action_key": action, "allowed": True})

    # --- Junior Director: same set as AD, but ownership-gated at runtime -
    # Note: unlock is AD-or-CEO only (UnlockerRoles), so JD does NOT get it.
    jd_actions = [
        "project.create",
        "project.edit",
        "project.delete",
        "script_versioning.lock",
        "asset_review_with_timecodes.request_changes",
    ] + [
        _stage_move_key(f, t)
        for f, t in _STAGE_TRANSITIONS
        if _stage_move_key(f, t) not in publish_actions
    ]
    for action in jd_actions:
        rows.append({"role_key": "junior_director", "action_key": action, "allowed": True})

    # --- Editor: edit owned projects only --------------------------------
    for action in ("project.edit",):
        rows.append({"role_key": "editor", "action_key": action, "allowed": True})

    # --- Crew / Viewer: read-only --------------------------------------
    # No mutating action_keys; the permission service only checks for VIEW
    # via the project-access path which is allowed for anyone with a
    # department_membership.

    return rows


TEMPLATE: dict[str, Any] = {
    "key": "content_creation",
    "name": "Content Creation",
    "description": (
        "Idea → published video pipeline. 11 stages, 6 roles, "
        "5 capabilities (script versioning, asset review with timecodes, "
        "location scouting, participant roster, event scheduling)."
    ),
    "is_system": True,
    "default_capabilities": [
        "script_versioning",
        "asset_review_with_timecodes",
        "location_scouting",
        "participant_roster",
        "event_scheduling",
    ],
    "default_stages": _STAGES,
    "default_roles": _ROLES,
    "default_role_permissions": _build_permissions(),
}


__all__ = ["TEMPLATE"]
