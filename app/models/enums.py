"""Postgres enums shared across models.

Enum *values* (lowercase strings) are what Postgres stores; the Python names
are uppercase by Python convention. Names of the DB types (`name=` kwarg on
SAEnum) are explicit so Alembic autogenerate produces stable migration code.

Adding a new value requires a follow-up migration with `ALTER TYPE … ADD VALUE`
— Alembic autogenerate cannot diff Postgres enums reliably, so write that
migration by hand.
"""

from __future__ import annotations

from enum import Enum, StrEnum

from sqlalchemy import Enum as SAEnum


def pg_enum(enum_cls: type[Enum], *, name: str) -> SAEnum:
    """Build a Postgres-native enum that stores the Python enum's *value*.

    Without `values_callable`, SQLAlchemy stores the enum member's `.name`
    (uppercase) in the DB; we want the lowercase `.value` so wire payloads,
    DB rows, and Python all agree on the same string form.
    """
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=True,
        values_callable=lambda cls: [member.value for member in cls],
    )


class Role(StrEnum):
    """User role.

    DEPRECATED for project work: superseded by `department_roles` +
    `department_role_permissions` in the DB. Only `Role.CEO` remains
    load-bearing — it's the global super-admin bit on `users.role` that
    short-circuits the permission service. The other values stay as a
    legacy shim until Phase D deletes them.
    """

    CEO = "ceo"
    ASSISTANT_DIRECTOR = "assistant_director"
    JUNIOR_DIRECTOR = "junior_director"
    EDITOR = "editor"
    CREW = "crew"
    VIEWER = "viewer"


class Category(StrEnum):
    """Project category. Placeholder list — confirm with CEO in Phase 0 close-out."""

    PROPERTY_TOUR = "property_tour"
    AGENT_INTRO = "agent_intro"
    NEIGHBOURHOOD = "neighbourhood"
    TESTIMONIAL = "testimonial"
    OTHER = "other"


class PipelineStage(StrEnum):
    """11-stage production pipeline.

    DEPRECATED: superseded by per-department `department_stages` rows.
    Values are kept as keys on the Content Creation template's stages so
    `project.stage::text == department_stage.key` still resolves cleanly
    during the Phase B backfill; Phase D drops both the enum and the
    legacy `projects.stage` mirror column.
    """

    IDEA = "idea"
    SCRIPT_DRAFTING = "script_drafting"
    SCRIPT_REVIEW = "script_review"
    SCRIPT_LOCKED = "script_locked"
    LOCATION_SCOUTING = "location_scouting"
    CASTING = "casting"
    SHOOT_SCHEDULED = "shoot_scheduled"
    SHOOT_DONE = "shoot_done"
    EDITING = "editing"
    FINAL_REVIEW = "final_review"
    APPROVED_PUBLISHED = "approved_published"


class EditStatus(StrEnum):
    """Lifecycle of a single edit version (cut)."""

    IN_REVIEW = "in_review"
    CHANGES_REQUESTED = "changes_requested"
    APPROVED = "approved"


class ShootStatus(StrEnum):
    """Lifecycle of a single shoot."""

    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    WRAPPED = "wrapped"


class TokenPurpose(StrEnum):
    """What a one-time token is for. Drives both TTL and email template choice."""

    INVITATION = "invitation"
    PASSWORD_RESET = "password_reset"


class BusinessMembershipStatus(StrEnum):
    """Lifecycle of a user's membership in a business."""

    INVITED = "invited"
    ACTIVE = "active"
    REVOKED = "revoked"


__all__ = [
    "BusinessMembershipStatus",
    "Category",
    "EditStatus",
    "PipelineStage",
    "Role",
    "ShootStatus",
    "TokenPurpose",
    "pg_enum",
]
