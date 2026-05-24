"""Per-department role (e.g. "Video Editor" inside Content Creation).

Roles are defined *per department*, not globally — Marketing has "Digital
Marketer", Content Creation has "Video Editor". The fixed top-level `Role`
enum stays for the CEO super-admin bit on `users.role`; everything else moves
to these per-department rows.

Permissions are flipped per `(role, action_key)` in
`department_role_permissions`.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DepartmentRoleModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "department_roles"
    __table_args__ = (
        UniqueConstraint("department_id", "key", name="uq_department_role_key"),
    )

    department_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
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
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


__all__ = ["DepartmentRoleModel"]
