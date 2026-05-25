"""Department — a unit of work inside a business.

A department is created either from a `DepartmentTemplateModel` (most common
path: pick "Content Creation", get pre-populated stages + roles) or empty.
The `template_key` is kept as a string mirror after creation — the
frontend reads it to decide which tab set + permission-action set this
department exposes (`features/projects/lib/projectTabs.ts`,
`features/departments/lib/permissionActionsByTemplate.ts`). The template's
defaults are *copied* into per-department rows so upstream template edits
never mutate live departments.

Archived departments stay queryable for history but are hidden in the UI.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DepartmentModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "departments"
    __table_args__ = (
        UniqueConstraint("business_id", "slug", name="uq_department_business_slug"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    template_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)

    # Per-noun label overrides copied from the template. Shape:
    # `{noun: {locale: label}}`. Used by the frontend `useDepartmentTerminology`
    # hook to render context-aware labels (e.g. "New lead" vs "New project").
    terminology: Mapped[dict[str, dict[str, str]]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )


__all__ = ["DepartmentModel"]
