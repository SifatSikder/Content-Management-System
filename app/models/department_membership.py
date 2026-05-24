"""Assigns a user (already a business member) one role inside a department.

A user can hold one role per department but may belong to multiple departments
inside the same business with different roles in each. The
`business_memberships` row is the prerequisite — without it, a user cannot
even see the department.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


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


__all__ = ["DepartmentMembershipModel"]
