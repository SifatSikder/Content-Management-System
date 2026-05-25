"""Pydantic DTOs for the project endpoints."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Category


class OwnerPublic(BaseModel):
    """Minimal user projection embedded in project responses for UI rendering."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    avatar_url: str | None = None


class StagePublic(BaseModel):
    """Embedded stage view — what the kanban column needs to render."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    name_i18n: dict[str, str]
    order_index: int
    is_terminal: bool
    color: str | None = None


class DepartmentEmbed(BaseModel):
    """Minimal department projection inlined on a project response.

    Carries `capabilities`, per-capability `capability_configs`, and
    `terminology` — everything the frontend needs to decide which tabs
    to render, how each capability tab should look, and what labels to
    use ("New project" vs "New lead"). Saves the frontend a second
    round-trip per project page.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    capabilities: list[str]
    capability_configs: dict[str, dict[str, Any]] = Field(default_factory=dict)
    terminology: dict[str, dict[str, str]] = Field(default_factory=dict)


class CreateProjectBody(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    category: Category
    department_id: uuid.UUID
    description: str | None = None
    due_date: date | None = None
    # Optional override — only honoured for admins. Defaults to current_user.
    owner_id: uuid.UUID | None = None
    # Optional: pick a stage other than the department's entry stage (rare).
    stage_id: uuid.UUID | None = None


class UpdateProjectBody(BaseModel):
    """All fields optional — PATCH semantics."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    category: Category | None = None
    due_date: date | None = None


class MoveStageBody(BaseModel):
    """Either `stage_id` (preferred) or `stage_key` (legacy)."""

    stage_id: uuid.UUID | None = None
    stage_key: str | None = None


class ProjectPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None
    category: Category
    business_id: uuid.UUID
    department_id: uuid.UUID
    stage_id: uuid.UUID
    stage: StagePublic
    department: DepartmentEmbed
    owner_id: uuid.UUID
    owner: OwnerPublic
    due_date: date | None
    script_locked_at: datetime | None
    script_locked_by: uuid.UUID | None
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
    "StagePublic",
    "UpdateProjectBody",
]
