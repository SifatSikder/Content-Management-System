"""Department template — a starting point for spinning up a new department.

Templates declare default stages, roles, and terminology. When a department
is created from a template the JSONB defaults are *copied* into per-department
`department_stages` / `department_roles` / `departments.terminology` rows, so
later edits to a template don't retroactively change live departments.

The set of feature tabs each template exposes is hardcoded on the frontend
(`frontend/src/features/projects/lib/projectTabs.ts`) — there is no
per-template "capabilities" JSONB anymore.

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

    default_stages: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    default_roles: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
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
