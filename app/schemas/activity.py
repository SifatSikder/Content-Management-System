"""Pydantic DTOs for the activity-feed endpoint."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ActorEmbed(BaseModel):
    """Minimal user projection inlined on every activity row.

    NULL if the actor was deleted (spec §10 PII redaction). The frontend
    falls back to "system" in that case.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class ActivityPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID | None
    actor_id: uuid.UUID | None
    actor: ActorEmbed | None = None
    action: str
    metadata_json: dict[str, Any]
    created_at: datetime


class ActivityListResponse(BaseModel):
    items: list[ActivityPublic]
    next_cursor: str | None = None


__all__ = ["ActivityListResponse", "ActivityPublic", "ActorEmbed"]
