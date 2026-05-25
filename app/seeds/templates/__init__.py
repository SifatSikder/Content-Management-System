"""Registry of department templates.

Each module in this package defines a single template dict with the structure:

    TEMPLATE = {
        "key": "content_creation",
        "name": "Content Creation",
        "description": "...",
        "is_system": True,
        "default_capabilities": ["script_versioning", ...],
        "default_stages": [
            {"key": "idea", "name_i18n": {"nl": "...", "en": "..."},
             "order_index": 0, "is_terminal": False, "color": "#…",
             "allowed_from_stage_keys": []},
            ...
        ],
        "default_roles": [
            {"key": "ceo", "name_i18n": {"nl": "...", "en": "..."}, "description": "..."},
            ...
        ],
        "default_role_permissions": [
            {"role_key": "ceo", "action_key": "project.create", "allowed": True},
            ...
        ],
    }

`allowed_from_stage_keys` is template-only: keys are resolved to ids when the
template is instantiated into a department (see
`app/services/department_service.py::create_department`).

`default_role_permissions` is also template-only — the live row is in
`department_role_permissions` (keyed by `(role_id, action_key)`), seeded at
instantiation time.
"""

from __future__ import annotations

from typing import Any

from app.seeds.templates import content_creation, marketing

TEMPLATES: dict[str, dict[str, Any]] = {
    content_creation.TEMPLATE["key"]: content_creation.TEMPLATE,
    marketing.TEMPLATE["key"]: marketing.TEMPLATE,
}


def all_templates() -> list[dict[str, Any]]:
    """Return every registered template definition. Order is insertion order."""
    return list(TEMPLATES.values())


def get_template(key: str) -> dict[str, Any]:
    """Return the template dict for `key` or raise KeyError."""
    return TEMPLATES[key]


__all__ = ["TEMPLATES", "all_templates", "get_template"]
