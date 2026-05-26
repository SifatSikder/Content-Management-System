"""Marketing — the second department template that proves the multi-business
abstraction.

A different stage list (sales funnel — lead_new → closed_won/lost), a
different role list (marketing_manager / digital_marketer / sdr), and a
single reused capability (`participant_roster`, now driving a lead list
instead of a cast list). The CEO can stand this up under any business
without any code change between Sons Real Estate's Content Creation and
this one — that's the Phase C exit-criterion proof.

The `participant_roster` capability gets a `kind: "lead"` config + a
`visible_fields` whitelist so the frontend can render a lead form instead
of the cast form. See `app/seeds/templates/content_creation.py` for the
parallel cast-mode config.
"""

from __future__ import annotations

from typing import Any

# ---------- stages -------------------------------------------------------
# Six stages: a basic outbound-sales funnel. `closed_won` and `closed_lost`
# are both terminal. Runtime source of truth — see `stage_registry`.

STAGES: list[dict[str, Any]] = [
    {
        "key": "lead_new",
        "name_i18n": {"nl": "Nieuwe lead", "en": "New lead"},
        "color": "#60a5fa",
        "allowed_from_stage_keys": [],
    },
    {
        "key": "qualified",
        "name_i18n": {"nl": "Gekwalificeerd", "en": "Qualified"},
        "color": "#38bdf8",
        "allowed_from_stage_keys": ["lead_new"],
    },
    {
        "key": "contacted",
        "name_i18n": {"nl": "Contact gemaakt", "en": "Contacted"},
        "color": "#fbbf24",
        "allowed_from_stage_keys": ["qualified"],
    },
    {
        "key": "meeting_scheduled",
        "name_i18n": {"nl": "Afspraak ingepland", "en": "Meeting scheduled"},
        "color": "#f59e0b",
        "allowed_from_stage_keys": ["contacted"],
    },
    {
        "key": "closed_won",
        "name_i18n": {"nl": "Gewonnen", "en": "Closed — won"},
        "color": "#22c55e",
        "is_terminal": True,
        "allowed_from_stage_keys": ["meeting_scheduled"],
    },
    {
        "key": "closed_lost",
        "name_i18n": {"nl": "Verloren", "en": "Closed — lost"},
        "color": "#ef4444",
        "is_terminal": True,
        # Lost is reachable from any active stage — leads die anywhere in the
        # funnel.
        "allowed_from_stage_keys": ["qualified", "contacted", "meeting_scheduled"],
    },
]


# ---------- roles --------------------------------------------------------
# Deliberately different from Content Creation to prove role definitions are
# per-department, not globally shared.

_ROLES: list[dict[str, Any]] = [
    {
        "key": "marketing_manager",
        "name_i18n": {"nl": "Marketing manager", "en": "Marketing Manager"},
        "description": "Owns the funnel — can move any lead to any stage including closed_won.",
    },
    {
        "key": "digital_marketer",
        "name_i18n": {"nl": "Digital marketeer", "en": "Digital Marketer"},
        "description": "Drives qualified leads through the funnel; can't close a deal.",
    },
    {
        "key": "sdr",
        "name_i18n": {"nl": "SDR", "en": "Sales Development Rep"},
        "description": "Front-of-funnel outreach. Owns lead_new → meeting_scheduled handoff.",
    },
]


# ---------- permission matrix -------------------------------------------
# Enumerate every valid (from, to) pair as a `stage.move:from->to` action.

STAGE_TRANSITIONS: list[tuple[str, str]] = [
    ("lead_new", "qualified"),
    ("qualified", "contacted"),
    ("contacted", "meeting_scheduled"),
    ("meeting_scheduled", "closed_won"),
    # closed_lost reachable from each active stage
    ("qualified", "closed_lost"),
    ("contacted", "closed_lost"),
    ("meeting_scheduled", "closed_lost"),
    # back-stage movement (mistakes happen; manager can override)
    ("qualified", "lead_new"),
    ("contacted", "qualified"),
    ("meeting_scheduled", "contacted"),
]

# Subset SDR is allowed to drive (front-of-funnel only; can't mark closed_*).
_SDR_TRANSITIONS: set[tuple[str, str]] = {
    ("lead_new", "qualified"),
    ("qualified", "contacted"),
    ("contacted", "meeting_scheduled"),
    ("qualified", "lead_new"),
    ("contacted", "qualified"),
    ("meeting_scheduled", "contacted"),
}


def _stage_move_key(from_key: str, to_key: str) -> str:
    return f"stage.move:{from_key}->{to_key}"


def _build_permissions() -> list[dict[str, Any]]:
    """Translate the role descriptions above into explicit `(role, action,
    allowed)` triples. Ownership predicates (e.g. "digital_marketer can only
    edit leads they own") stay as runtime checks in `permission_service`.
    """
    rows: list[dict[str, Any]] = []

    # --- Marketing Manager: everything ----------------------------------
    manager_actions = [
        "project.create",
        "project.edit",
        "project.delete",
        "participant_roster.add",
        "participant_roster.edit",
        "participant_roster.remove",
    ] + [_stage_move_key(f, t) for f, t in STAGE_TRANSITIONS]
    for action in manager_actions:
        rows.append({"role_key": "marketing_manager", "action_key": action, "allowed": True})

    # --- Digital Marketer: non-terminal moves + edit own ----------------
    # Closed-* (terminal) transitions are excluded — closing a deal is the
    # Marketing Manager's call.
    terminal_actions = {
        _stage_move_key("meeting_scheduled", "closed_won"),
        _stage_move_key("qualified", "closed_lost"),
        _stage_move_key("contacted", "closed_lost"),
        _stage_move_key("meeting_scheduled", "closed_lost"),
    }
    marketer_actions = [
        "project.create",
        "project.edit",
        "participant_roster.add",
        "participant_roster.edit",
    ] + [
        _stage_move_key(f, t)
        for f, t in STAGE_TRANSITIONS
        if _stage_move_key(f, t) not in terminal_actions
    ]
    for action in marketer_actions:
        rows.append({"role_key": "digital_marketer", "action_key": action, "allowed": True})

    # --- SDR: narrow front-of-funnel + edit own --------------------------
    sdr_actions = [
        "project.create",
        "project.edit",
        "participant_roster.add",
        "participant_roster.edit",
    ] + [_stage_move_key(f, t) for f, t in _SDR_TRANSITIONS]
    for action in sdr_actions:
        rows.append({"role_key": "sdr", "action_key": action, "allowed": True})

    return rows


# ---------- terminology --------------------------------------------------
# Templates carry UI terminology overrides so generic nouns render the
# right label per template ("Lead" vs "Project").

_TERMINOLOGY: dict[str, dict[str, str]] = {
    # Each entry maps a generic noun to its in-context label, per locale.
    # The frontend reads these with a small fallback chain to the default
    # i18n string when a template doesn't override.
    "project": {"en": "Lead", "nl": "Lead"},
    "projects": {"en": "Leads", "nl": "Leads"},
    "create_project": {"en": "New lead", "nl": "Nieuwe lead"},
    "roster_entry": {"en": "Contact", "nl": "Contactpersoon"},
}


TEMPLATE: dict[str, Any] = {
    "key": "marketing",
    "name": "Marketing",
    "description": (
        "Outbound sales funnel. 6 stages (new lead → won/lost), 3 roles. "
        "The participant_roster tab renders in lead mode via the hardcoded "
        "template_key → tabs map on the frontend."
    ),
    "is_system": True,
    "default_terminology": _TERMINOLOGY,
    "default_stages": STAGES,
    "default_roles": _ROLES,
    "default_role_permissions": _build_permissions(),
}


__all__ = ["STAGES", "STAGE_TRANSITIONS", "TEMPLATE"]
