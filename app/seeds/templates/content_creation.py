"""Content Creation — the department template carrying the original Sons Real
Estate real-estate video pipeline (11 stages, 6 roles).

`STAGES` and `STAGE_TRANSITIONS` are the **runtime** source of truth for the
kanban + stage-transition permissions in any Content Creation department. The
DB-backed `department_stages` table was removed (2026-05-26 follow-up to the
capability registry teardown); per-department customisation moved back into
code per template, mirroring the pre-Phase B `PipelineStage` enum world.
Roles, role descriptions, and the permission matrix are still seeded into
`department_roles` + `department_role_permissions` at instantiation so each
business can tune who can do what without a code edit.
"""

from __future__ import annotations

from typing import Any

# ---------- stages -------------------------------------------------------
# Order is significant — index = kanban column order. Every stage entry on
# every department of this template references this list at runtime via
# `app.services.stage_registry`.

STAGES: list[dict[str, Any]] = [
    {
        "key": "location_scouting",
        "name_i18n": {"nl": "Locatie scouten", "en": "Location scouting"},
        "color": "#fbbf24",
        "allowed_from_stage_keys": [],
    },
    {
        "key": "draft_idea",
        "name_i18n": {"nl": "Concept idee", "en": "Draft idea"},
        "color": "#94a3b8",
        # Auto-advance fires when `Lock Location` is pressed.
        "allowed_from_stage_keys": ["location_scouting"],
    },
    {
        "key": "script_drafting",
        "name_i18n": {"nl": "Script schrijven", "en": "Script drafting"},
        "color": "#60a5fa",
        # `Lock Idea` advances here. Bounce-back from review for revisions
        # is also valid.
        "allowed_from_stage_keys": ["draft_idea", "script_review"],
    },
    {
        "key": "script_review",
        "name_i18n": {"nl": "Script review", "en": "Script review"},
        "color": "#38bdf8",
        "allowed_from_stage_keys": ["script_drafting"],
    },
    {
        "key": "casting",
        "name_i18n": {"nl": "Casting", "en": "Casting"},
        "color": "#f59e0b",
        # `Lock Script` advances here from drafting *or* review.
        # Locking is now a project property (`script_locked_at/by`), not a stage.
        "allowed_from_stage_keys": ["script_drafting", "script_review"],
    },
    {
        "key": "shoot_schedule",
        "name_i18n": {"nl": "Opname plannen", "en": "Shoot schedule"},
        "color": "#fb7185",
        # `Lock Casting` advances here.
        "allowed_from_stage_keys": ["casting"],
    },
    {
        "key": "shoot_in_progress",
        "name_i18n": {"nl": "Opname bezig", "en": "Shoot in progress"},
        "color": "#ef4444",
        # `shoot_service` advances here when first shoot transitions to IN_PROGRESS.
        "allowed_from_stage_keys": ["shoot_schedule"],
    },
    {
        "key": "shoot_done",
        "name_i18n": {"nl": "Opname klaar", "en": "Shoot done"},
        "color": "#f43f5e",
        "allowed_from_stage_keys": ["shoot_in_progress"],
    },
    {
        "key": "editing",
        "name_i18n": {"nl": "Montage", "en": "Editing"},
        "color": "#a78bfa",
        # Raw-cut submission on shoot_done card advances here.
        # `request_changes` from edit_review also bumps back here.
        "allowed_from_stage_keys": ["shoot_done", "edit_review"],
    },
    {
        "key": "edit_review",
        "name_i18n": {"nl": "Cut review", "en": "Edit review"},
        "color": "#8b5cf6",
        "allowed_from_stage_keys": ["editing"],
    },
    {
        "key": "approved_published",
        "name_i18n": {"nl": "Goedgekeurd & gepubliceerd", "en": "Approved & published"},
        "color": "#22c55e",
        "is_terminal": True,
        "allowed_from_stage_keys": ["edit_review", "editing"],
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

STAGE_TRANSITIONS: list[tuple[str, str]] = [
    ("location_scouting", "draft_idea"),
    ("draft_idea", "script_drafting"),
    ("script_drafting", "script_review"),
    ("script_review", "script_drafting"),
    ("script_drafting", "casting"),
    ("script_review", "casting"),
    ("casting", "shoot_schedule"),
    ("shoot_schedule", "shoot_in_progress"),
    ("shoot_in_progress", "shoot_done"),
    ("shoot_done", "editing"),
    ("editing", "edit_review"),
    ("edit_review", "editing"),
    ("edit_review", "approved_published"),
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
        _stage_move_key("edit_review", "approved_published"),
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
        "location.lock",
        "casting.lock",
        "raw_cut.submit",
        "department.edit_handoffs",
        "idea_versioning.lock",
        "idea_versioning.signoff",
    ] + [_stage_move_key(f, t) for f, t in STAGE_TRANSITIONS]
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
        "location.lock",
        "casting.lock",
        "raw_cut.submit",
        "department.edit_handoffs",
        "idea_versioning.lock",
        "idea_versioning.signoff",
    ] + [
        _stage_move_key(f, t)
        for f, t in STAGE_TRANSITIONS
        if _stage_move_key(f, t) not in publish_actions
    ]
    for action in ad_actions:
        rows.append({"role_key": "assistant_director", "action_key": action, "allowed": True})

    # --- Junior Director: same set as AD, but ownership-gated at runtime -
    # Note: unlock is AD-or-CEO only (UnlockerRoles), so JD does NOT get it.
    # JD can submit raw cuts (shoot phase is theirs) but not lock location
    # or casting (those are the Asst CEO's calls).
    jd_actions = [
        "project.create",
        "project.edit",
        "project.delete",
        "script_versioning.lock",
        "asset_review_with_timecodes.request_changes",
        "raw_cut.submit",
        "idea_versioning.signoff",
    ] + [
        _stage_move_key(f, t)
        for f, t in STAGE_TRANSITIONS
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


# ---------- terminology --------------------------------------------------

# Terminology defaults: empty → frontend falls back to the legacy
# `project_detail.*` i18n strings ("Project", "New project", "Cast member").
_TERMINOLOGY: dict[str, dict[str, str]] = {}


TEMPLATE: dict[str, Any] = {
    "key": "content_creation",
    "name": "Content Creation",
    "description": (
        "Idea → published video pipeline. 11 stages, 6 roles. Feature tabs "
        "are hardcoded in `frontend/src/features/projects/lib/projectTabs.ts` "
        "(Script, Locations, Casting, Shoots, Edits)."
    ),
    "is_system": True,
    "default_terminology": _TERMINOLOGY,
    "default_stages": STAGES,
    "default_roles": _ROLES,
    "default_role_permissions": _build_permissions(),
}


__all__ = ["STAGES", "STAGE_TRANSITIONS", "TEMPLATE"]
