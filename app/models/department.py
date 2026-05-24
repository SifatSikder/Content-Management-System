"""Department — a unit of work inside a business.

A department is created either from a `DepartmentTemplateModel` (most common
path: pick "Content Creation", get pre-populated stages + roles) or empty.
The `template_key` is kept as a string mirror after creation for analytics
only — the template's defaults are *copied* into per-department rows so
upstream template edits never mutate live departments.

`capabilities` is an editable JSONB array of capability keys (e.g.
`["script_versioning", "asset_review_with_timecodes"]`); the registry in
`app/capabilities/registry.py` maps each key to a backend router + frontend
tab. Archived departments stay queryable for history but are hidden in the UI.
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

    capabilities: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )


__all__ = ["DepartmentModel"]
