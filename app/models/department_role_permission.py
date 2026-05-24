"""Per-role, per-action permission flag.

`action_key` is an opaque string namespace owned by the capability registry —
e.g. `stage.move:script_locked->editing`, `project.create`,
`script_versioning.lock`. The capability's `default_role_permissions` block
seeds these rows when a department adopts the capability; the CEO can flip
individual bits via the permission-matrix editor afterwards.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DepartmentRolePermissionModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "department_role_permissions"
    __table_args__ = (
        UniqueConstraint(
            "department_role_id",
            "action_key",
            name="uq_department_role_permission_action",
        ),
    )

    department_role_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("department_roles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    action_key: Mapped[str] = mapped_column(String(128), nullable=False)
    allowed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )


__all__ = ["DepartmentRolePermissionModel"]
