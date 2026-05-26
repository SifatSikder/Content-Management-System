"""Pydantic DTOs for the project endpoints."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Category


class OwnerPublic(BaseModel):
    """Minimal user projection embedded in project responses for UI rendering."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    avatar_url: str | None = None


class DepartmentEmbed(BaseModel):
    """Minimal department projection inlined on a project response.

    Carries `template_key` (the frontend uses it to pick the tab set + the
    participant_roster cast/lead mode) and `terminology` (per-department i18n
    overrides). The shape used to also include `capabilities` +
    `capability_configs`; both were removed when capability gating moved to
    a hardcoded `template_key → tabs` map on the frontend.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    template_key: str | None = None
    terminology: dict[str, dict[str, str]] = Field(default_factory=dict)


class CreateProjectBody(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    category: Category
    department_id: uuid.UUID
    description: str | None = None
    due_date: date | None = None
    # Optional override — only honoured for admins. Defaults to current_user.
    owner_id: uuid.UUID | None = None
    # Optional: pick a stage other than the department template's entry stage.
    stage_key: str | None = Field(default=None, min_length=1, max_length=120)


class UpdateProjectBody(BaseModel):
    """All fields optional — PATCH semantics."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    category: Category | None = None
    due_date: date | None = None


class MoveStageBody(BaseModel):
    """Target stage key inside the project's department template."""

    stage_key: str = Field(min_length=1, max_length=120)


class ProjectPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None
    category: Category
    business_id: uuid.UUID
    department_id: uuid.UUID
    stage_key: str
    department: DepartmentEmbed
    owner_id: uuid.UUID
    owner: OwnerPublic
    due_date: date | None
    script_locked_at: datetime | None
    script_locked_by: uuid.UUID | None
    location_locked_at: datetime | None = None
    location_locked_by: uuid.UUID | None = None
    casting_locked_at: datetime | None = None
    casting_locked_by: uuid.UUID | None = None
    drive_folder_id: str | None = None
    drive_folder_url: str | None = None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class ProjectListResponse(BaseModel):
    items: list[ProjectPublic]
    next_cursor: str | None = None


__all__ = [
    "CreateProjectBody",
    "DepartmentEmbed",
    "MoveStageBody",
    "OwnerPublic",
    "ProjectListResponse",
    "ProjectPublic",
    "UpdateProjectBody",
]
