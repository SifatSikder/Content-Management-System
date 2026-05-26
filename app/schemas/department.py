"""Pydantic DTOs for departments, stages, roles, permissions, and
department memberships (Phase A)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import BusinessMembershipStatus
from app.schemas.auth import UserPublic

# --- Templates -----------------------------------------------------------


class DepartmentTemplatePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    name: str
    description: str | None = None
    default_terminology: dict[str, dict[str, str]] = Field(default_factory=dict)
    is_system: bool
    created_at: datetime


# --- Departments ---------------------------------------------------------


class CreateDepartmentBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        pattern=r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$",
    )
    template_key: str | None = Field(default=None, max_length=64)


class UpdateDepartmentBody(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)


class DepartmentPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    business_id: uuid.UUID
    template_key: str | None = None
    name: str
    slug: str
    terminology: dict[str, dict[str, str]] = Field(default_factory=dict)
    archived_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class DepartmentListResponse(BaseModel):
    items: list[DepartmentPublic]


class MeDepartmentEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    business_id: uuid.UUID
    name: str
    slug: str
    role_key: str | None = None
    role_name_i18n: dict[str, str] | None = None
    template_key: str | None = None
    # Surface the department's terminology so pages like /projects that
    # only have a MeDepartmentEntry in hand can render context-aware labels
    # ("New lead" vs "New project") without a follow-up GET /departments/{id}.
    terminology: dict[str, dict[str, str]] = Field(default_factory=dict)


class MeDepartmentsResponse(BaseModel):
    items: list[MeDepartmentEntry]


# --- Stages --------------------------------------------------------------


class CreateStageBody(BaseModel):
    key: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9](?:[a-z0-9_]*[a-z0-9])?$",
    )
    name_i18n: dict[str, str] = Field(default_factory=dict)
    order_index: int = 0
    is_terminal: bool = False
    color: str | None = Field(default=None, max_length=32)
    allowed_from_stage_ids: list[uuid.UUID] = Field(default_factory=list)


class UpdateStageBody(BaseModel):
    name_i18n: dict[str, str] | None = None
    order_index: int | None = None
    is_terminal: bool | None = None
    color: str | None = Field(default=None, max_length=32)
    allowed_from_stage_ids: list[uuid.UUID] | None = None


class StagePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    department_id: uuid.UUID
    business_id: uuid.UUID
    key: str
    name_i18n: dict[str, str]
    order_index: int
    is_terminal: bool
    color: str | None = None
    allowed_from_stage_ids: list[str]
    created_at: datetime
    updated_at: datetime


class StageListResponse(BaseModel):
    items: list[StagePublic]


# --- Roles ---------------------------------------------------------------


class CreateRoleBody(BaseModel):
    key: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9](?:[a-z0-9_]*[a-z0-9])?$",
    )
    name_i18n: dict[str, str] = Field(default_factory=dict)
    description: str | None = None


class UpdateRoleBody(BaseModel):
    name_i18n: dict[str, str] | None = None
    description: str | None = None


class RolePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    department_id: uuid.UUID
    business_id: uuid.UUID
    key: str
    name_i18n: dict[str, str]
    description: str | None = None
    created_at: datetime
    updated_at: datetime


class RoleListResponse(BaseModel):
    items: list[RolePublic]


# --- Role permissions ----------------------------------------------------


class PermissionPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    department_role_id: uuid.UUID
    action_key: str
    allowed: bool


class PermissionListResponse(BaseModel):
    items: list[PermissionPublic]


class UpsertPermissionBody(BaseModel):
    action_key: str = Field(min_length=1, max_length=128)
    allowed: bool


# --- Department memberships ---------------------------------------------


class AssignDepartmentMemberBody(BaseModel):
    user_id: uuid.UUID
    role_id: uuid.UUID


class DepartmentMembershipPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    department_id: uuid.UUID
    business_id: uuid.UUID
    user_id: uuid.UUID
    role_id: uuid.UUID
    user: UserPublic
    role: RolePublic
    # Joined off the matching `business_memberships` row — needed so the
    # FE can render an Active/Inactive/Pending badge and address the row
    # via the PATCH endpoint without a second round-trip.
    business_membership_id: uuid.UUID | None = None
    business_membership_status: BusinessMembershipStatus | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm_row(cls, row: object) -> DepartmentMembershipPublic:
        """Construct from a `DepartmentMembershipModel` with its
        `business_membership` relation eagerloaded.

        Pydantic's `from_attributes` can't reach into `row.business_membership.id`
        / `.status` directly because they're properties on the related
        ORM object; we hoist them explicitly here.
        """
        bm = getattr(row, "business_membership", None)
        return cls.model_validate(
            {
                "id": row.id,
                "department_id": row.department_id,
                "business_id": row.business_id,
                "user_id": row.user_id,
                "role_id": row.role_id,
                "user": row.user,
                "role": row.role,
                "business_membership_id": bm.id if bm is not None else None,
                "business_membership_status": bm.status if bm is not None else None,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            },
            from_attributes=True,
        )


class InviteDepartmentMemberBody(BaseModel):
    """Request body for the orchestrated invite-to-department flow.

    The Next.js BFF layer (`/api/businesses/[slug]/departments/[id]/invite`)
    is the actual entry point — it find-or-creates the platform user, mints
    the invitation token, sends the email, then forwards `{user_id, role_id}`
    to the existing assign-membership FastAPI endpoint. This DTO documents
    the shape the BFF accepts; FastAPI itself only sees `user_id + role_id`.
    """

    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    role_id: uuid.UUID


class DepartmentMembershipListResponse(BaseModel):
    items: list[DepartmentMembershipPublic]


__all__ = [
    "AssignDepartmentMemberBody",
    "CreateDepartmentBody",
    "CreateRoleBody",
    "CreateStageBody",
    "DepartmentListResponse",
    "DepartmentMembershipListResponse",
    "DepartmentMembershipPublic",
    "DepartmentPublic",
    "DepartmentTemplatePublic",
    "MeDepartmentEntry",
    "MeDepartmentsResponse",
    "PermissionListResponse",
    "PermissionPublic",
    "RoleListResponse",
    "RolePublic",
    "StageListResponse",
    "StagePublic",
    "UpdateDepartmentBody",
    "UpdateRoleBody",
    "UpdateStageBody",
    "UpsertPermissionBody",
]
