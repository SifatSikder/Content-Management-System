"""Assigns a user one role inside a department.

A user can hold one role per department but may belong to multiple departments
inside the same business with different roles in each. The matching
`business_memberships` row is auto-managed by `assign_department_member` /
`remove_department_member`: it is created the first time a user is added to
any department in a business and revoked when their last department
membership in that business is removed.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.department_role import DepartmentRoleModel
    from app.models.user import UserModel


class DepartmentMembershipModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "department_memberships"
    __table_args__ = (
        UniqueConstraint(
            "department_id", "user_id", name="uq_department_membership_user"
        ),
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
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("department_roles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # `lazy="raise"` keeps callers honest — `list_department_memberships`
    # selectinloads both relations; anything that forgets explodes loudly
    # instead of silently issuing N+1 queries.
    user: Mapped[UserModel] = relationship("UserModel", lazy="raise")
    role: Mapped[DepartmentRoleModel] = relationship(
        "DepartmentRoleModel", lazy="raise"
    )


__all__ = ["DepartmentMembershipModel"]
