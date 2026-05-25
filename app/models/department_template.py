"""Department template — a starting point for spinning up a new department.

Templates declare default capabilities, stages, and roles. When a department
is created from a template the JSONB defaults are *copied* into per-department
`department_stages` / `department_roles` / `departments.capabilities` rows, so
later edits to a template don't retroactively change live departments.

`is_system` templates ship with the product and can't be deleted by users.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DepartmentTemplateModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "department_templates"

    key: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    default_capabilities: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    default_stages: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    default_roles: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )

    # Per-capability config — `{capability_key: {kind, visible_fields, …}}`.
    # Copied into `departments.capability_configs` at instantiation. Phase C
    # introduced this to make `participant_roster` reusable for both cast
    # lists and lead lists; future capabilities can carry their own config.
    default_capability_configs: Mapped[dict[str, dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )

    # Per-noun UI labels — `{noun: {locale: label}}`. Overrides the
    # default i18n strings inside this template's departments (e.g. "Lead"
    # instead of "Project" in Marketing). See the frontend's
    # `useDepartmentTerminology` hook.
    default_terminology: Mapped[dict[str, dict[str, str]]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )

    is_system: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )


__all__ = ["DepartmentTemplateModel"]
