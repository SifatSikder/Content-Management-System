"""Pydantic DTOs for the activity-feed endpoint."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ActivityPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID | None
    actor_id: uuid.UUID | None
    action: str
    metadata_json: dict[str, Any]
    created_at: datetime


class ActivityListResponse(BaseModel):
    items: list[ActivityPublic]
    next_cursor: str | None = None


__all__ = ["ActivityListResponse", "ActivityPublic"]
