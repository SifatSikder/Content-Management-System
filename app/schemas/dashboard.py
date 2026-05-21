"""Pydantic DTOs for /dashboard/* endpoints (Phase 3 Task 3.2)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import PipelineStage


class AwaitingItemPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    project_id: uuid.UUID
    project_title: str
    stage: PipelineStage
    cut_id: uuid.UUID
    cut_version: int
    uploaded_at: datetime
    uploader_id: uuid.UUID | None


class StageCountPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    stage: PipelineStage
    count: int


class StuckProjectPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    project_id: uuid.UUID
    project_title: str
    stage: PipelineStage
    owner_id: uuid.UUID
    owner_name: str
    last_activity_at: datetime | None
    days_idle: int


class ThroughputBucketPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    week_start: datetime
    count: int


class TimeInStagePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    stage: PipelineStage
    sample_size: int
    avg_days: float | None
    max_days: float | None


__all__ = [
    "AwaitingItemPublic",
    "StageCountPublic",
    "StuckProjectPublic",
    "ThroughputBucketPublic",
    "TimeInStagePublic",
]
