"""Pydantic DTOs for the project endpoints."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Category, PipelineStage


class OwnerPublic(BaseModel):
    """Minimal user projection embedded in project responses for UI rendering."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    avatar_url: str | None = None


class CreateProjectBody(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    category: Category
    description: str | None = None
    due_date: date | None = None
    # Optional override — only honoured for admins. Defaults to current_user.
    owner_id: uuid.UUID | None = None


class UpdateProjectBody(BaseModel):
    """All fields optional — PATCH semantics."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    category: Category | None = None
    due_date: date | None = None


class MoveStageBody(BaseModel):
    stage: PipelineStage


class ProjectPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None
    category: Category
    stage: PipelineStage
    owner_id: uuid.UUID
    owner: OwnerPublic
    due_date: date | None
    script_locked_at: datetime | None
    script_locked_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class ProjectListResponse(BaseModel):
    items: list[ProjectPublic]
    next_cursor: str | None = None


__all__ = [
    "CreateProjectBody",
    "MoveStageBody",
    "OwnerPublic",
    "ProjectListResponse",
    "ProjectPublic",
    "UpdateProjectBody",
]
