"""Per-department, per-stage assignment rules.

Each row says: "when a project in this department enters this stage,
auto-assign one row to `project_stage_assignments` for every user
currently holding any of the roles in `role_ids`."

Seeded from the template's `DEFAULT_STAGE_HANDOFFS` at instantiation
(resolving role keys to role ids in this department); edited from the
Department settings UI thereafter.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DepartmentStageHandoffModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "department_stage_handoffs"
    __table_args__ = (
        UniqueConstraint(
            "department_id", "stage_key", name="uq_department_stage_handoff"
        ),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stage_key: Mapped[str] = mapped_column(String(120), nullable=False)
    # JSONB array of department_role UUIDs (stored as strings). Empty
    # list = no auto-assignees on entry.
    role_ids: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )


__all__ = ["DepartmentStageHandoffModel"]
