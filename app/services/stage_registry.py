"""In-code source of truth for department stages, keyed by template.

Pre-Phase B, stages were a hardcoded Postgres enum (`PipelineStage`). Phase B
moved them into the `department_stages` table so each business could
customise stages per-department at runtime. The 2026-05-26 follow-up to the
capability registry teardown reverses that decision: the editor was a
footgun (adding a stage in the UI doesn't auto-wire the `stage.move:*`
permission rows, capability gating, or any code that reacts to a project
landing on the stage), and future non-kanban departments wouldn't use stages
at all. Stages are now code-only constants per template.

The DB still holds:
  * `projects.stage_key` — which stage each project sits on
  * `department_role_permissions` — including `stage.move:<from>-><to>` rows
    seeded from the template at department instantiation

Everything stage-shaped (kanban columns, allowed transitions, names, colors)
comes from this module at runtime.
"""

from __future__ import annotations

from typing import Any

from app.seeds.templates import content_creation, marketing

# Mirror frontend `features/projects/lib/stagesByTemplate.ts`. When you add a
# stage here, also add it there — same trade-off as
# `permissionActionsByTemplate.ts`.
STAGES_BY_TEMPLATE: dict[str, list[dict[str, Any]]] = {
    content_creation.TEMPLATE["key"]: content_creation.STAGES,
    marketing.TEMPLATE["key"]: marketing.STAGES,
}


def get_stages(template_key: str | None) -> list[dict[str, Any]]:
    """Return the stage list for `template_key`, or an empty list if unknown.

    Returning `[]` for an unregistered template_key keeps callers simple: a
    department with `template_key=None` (legacy) or with a template we don't
    ship code for renders an empty kanban rather than 500-ing.
    """
    if template_key is None:
        return []
    return STAGES_BY_TEMPLATE.get(template_key, [])


def get_stage(template_key: str | None, stage_key: str) -> dict[str, Any] | None:
    """Return the stage spec for `(template_key, stage_key)` or None."""
    for spec in get_stages(template_key):
        if spec.get("key") == stage_key:
            return spec
    return None


def first_stage_key(template_key: str | None) -> str | None:
    """The entry stage for new projects in this template. None if no stages."""
    stages = get_stages(template_key)
    return stages[0].get("key") if stages else None


def is_known_stage(template_key: str | None, stage_key: str) -> bool:
    return get_stage(template_key, stage_key) is not None


def allowed_sources_for(template_key: str | None, stage_key: str) -> list[str]:
    """Stage keys that can move *into* `stage_key`.

    Empty list for entry stages or unknown targets.
    """
    spec = get_stage(template_key, stage_key)
    if spec is None:
        return []
    return list(spec.get("allowed_from_stage_keys", []) or [])


__all__ = [
    "STAGES_BY_TEMPLATE",
    "allowed_sources_for",
    "first_stage_key",
    "get_stage",
    "get_stages",
    "is_known_stage",
]
