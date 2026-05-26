"""Pydantic DTOs for the per-stage project assignment endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.project import OwnerPublic


class AssignmentPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    stage_key: str
    user_id: uuid.UUID
    user: OwnerPublic
    slot_key: str | None
    assigned_at: datetime
    assigned_by: uuid.UUID | None


class AssignmentListResponse(BaseModel):
    items: list[AssignmentPublic]


class AddAssignmentBody(BaseModel):
    user_id: uuid.UUID
