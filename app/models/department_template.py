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

    is_system: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )


__all__ = ["DepartmentTemplateModel"]
