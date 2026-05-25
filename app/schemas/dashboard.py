"""Pydantic DTOs for /dashboard/* endpoints (Phase 3 Task 3.2).

Phase B: `stage` is the department stage *key* (a free-form string) rather
than the legacy `PipelineStage` enum. Other templates with different stage
sets surface their own keys here.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AwaitingItemPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    project_id: uuid.UUID
    project_title: str
    stage: str
    cut_id: uuid.UUID
    cut_version: int
    uploaded_at: datetime
    uploader_id: uuid.UUID | None


class StageCountPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    stage: str
    count: int


class StuckProjectPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    project_id: uuid.UUID
    project_title: str
    stage: str
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

    stage: str
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
