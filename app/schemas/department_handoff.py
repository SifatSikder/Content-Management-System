"""Pydantic DTOs for the per-department stage handoff endpoints."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field


class StageHandoffPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    department_id: uuid.UUID
    stage_key: str
    role_ids: list[uuid.UUID]


class StageHandoffListResponse(BaseModel):
    items: list[StageHandoffPublic]


class UpsertStageHandoffBody(BaseModel):
    stage_key: str = Field(min_length=1, max_length=120)
    role_ids: list[uuid.UUID] = Field(default_factory=list)
