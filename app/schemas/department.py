"""Pydantic DTOs for departments, stages, roles, permissions, and
department memberships (Phase A)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.auth import UserPublic

# --- Templates -----------------------------------------------------------


class DepartmentTemplatePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    name: str
    description: str | None = None
    default_capabilities: list[str]
    default_capability_configs: dict[str, dict[str, Any]] = Field(default_factory=dict)
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
    capabilities: list[str] | None = None


class DepartmentPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    business_id: uuid.UUID
    template_key: str | None = None
    name: str
    slug: str
    capabilities: list[str]
    capability_configs: dict[str, dict[str, Any]] = Field(default_factory=dict)
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
    # Phase C: surface the department's terminology + capability configs so
    # pages like /projects that only have a MeDepartmentEntry in hand can
    # still render context-aware labels ("New lead" vs "New project")
    # without a follow-up GET /departments/{id}.
    terminology: dict[str, dict[str, str]] = Field(default_factory=dict)
    capability_configs: dict[str, dict[str, Any]] = Field(default_factory=dict)


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
    created_at: datetime
    updated_at: datetime


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
