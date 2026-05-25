"""Capability registry.

Each entry maps `capability_key` → metadata + routers. The registry is the
single source of truth for what backend surface a department exposes when it
enables a capability — `app/main.py` iterates this dict at startup to mount
every capability's routers, and `permission_service` consults the per-action
`permission_actions` list to validate template seeding.

Capability modules are intentionally thin wrappers: they re-export the
existing Phase-1 routers from `app/routes/*.py` under a new namespace so we
get the registry shape without rewriting working code. Moving the underlying
implementation (models + services) into per-capability subpackages is a Phase
D follow-up — for Phase B the goal is just the registry abstraction.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter

from app.capabilities.asset_review_with_timecodes import router as asset_review_module
from app.capabilities.event_scheduling import router as event_scheduling_module
from app.capabilities.location_scouting import router as location_scouting_module
from app.capabilities.participant_roster import router as participant_roster_module
from app.capabilities.script_versioning import router as script_versioning_module


@dataclass(frozen=True)
class Capability:
    """One capability's manifest. The runtime registry holds these by key."""

    key: str
    name: str
    routers: tuple[APIRouter, ...]
    permission_actions: tuple[str, ...]
    event_keys: tuple[str, ...]
    default_role_permissions: dict[str, list[str]] = field(default_factory=dict)
    """role_key -> [action_key, …] that the capability seeds when first
    installed into a template. Phase B uses the template's
    `default_role_permissions` for this — capabilities can still declare
    their own defaults for templates that wire them in later."""


REGISTRY: dict[str, Capability] = {
    "script_versioning": Capability(
        key="script_versioning",
        name="Script versioning",
        routers=(
            script_versioning_module.projects_router,
            script_versioning_module.scripts_router,
        ),
        permission_actions=(
            "script_versioning.lock",
            "script_versioning.unlock",
        ),
        event_keys=("script_submitted", "script_locked"),
    ),
    "asset_review_with_timecodes": Capability(
        key="asset_review_with_timecodes",
        name="Asset review with timecodes",
        routers=(
            asset_review_module.projects_router,
            asset_review_module.edits_router,
        ),
        permission_actions=(
            "asset_review_with_timecodes.approve",
            "asset_review_with_timecodes.request_changes",
        ),
        event_keys=(
            "cut_uploaded",
            "cut_comment",
            "cut_approved",
            "cut_changes_requested",
        ),
    ),
    "location_scouting": Capability(
        key="location_scouting",
        name="Location scouting",
        routers=(
            location_scouting_module.projects_router,
            location_scouting_module.locations_router,
        ),
        permission_actions=(),
        event_keys=(),
    ),
    "participant_roster": Capability(
        key="participant_roster",
        name="Participant roster",
        routers=(
            participant_roster_module.projects_router,
            participant_roster_module.cast_router,
        ),
        permission_actions=(),
        event_keys=(),
    ),
    "event_scheduling": Capability(
        key="event_scheduling",
        name="Event scheduling",
        routers=(
            event_scheduling_module.projects_router,
            event_scheduling_module.shoots_router,
        ),
        permission_actions=(),
        event_keys=(),
    ),
}


def all_capabilities() -> Iterable[Capability]:
    return REGISTRY.values()


def get(key: str) -> Capability:
    return REGISTRY[key]


def routers_for(keys: Iterable[str]) -> list[APIRouter]:
    """Return the FastAPI routers for the given capability keys."""
    out: list[APIRouter] = []
    for key in keys:
        cap = REGISTRY.get(key)
        if cap is None:
            continue
        out.extend(cap.routers)
    return out


def known_event_keys() -> set[str]:
    """Union of every event key declared by every capability."""
    keys: set[str] = set()
    for cap in REGISTRY.values():
        keys.update(cap.event_keys)
    return keys


__all__: list[Any] = [
    "REGISTRY",
    "Capability",
    "all_capabilities",
    "get",
    "known_event_keys",
    "routers_for",
]
