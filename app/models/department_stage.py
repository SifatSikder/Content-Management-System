"""Per-department workflow stages.

Each stage is one column in the kanban for its department. Projects reference
a stage by **id** (not by name) so renames are safe. `allowed_from_stage_ids`
is an explicit JSONB array of stage_ids that may transition *into* this one;
an empty array means "any stage is a valid predecessor" (used for entry stages
like "Inbox"/"Idea").

`name_i18n` stores localised display names: `{"nl": "...", "en": "..."}`.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DepartmentStageModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "department_stages"
    __table_args__ = (
        UniqueConstraint("department_id", "key", name="uq_department_stage_key"),
    )

    department_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Denormalised for RLS — child tables under a department share the
    # business_id of their parent for cheap policy filtering.
    business_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    key: Mapped[str] = mapped_column(String(64), nullable=False)
    name_i18n: Mapped[dict[str, str]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_terminal: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    color: Mapped[str | None] = mapped_column(String(32), nullable=True)
    allowed_from_stage_ids: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )


__all__ = ["DepartmentStageModel"]
