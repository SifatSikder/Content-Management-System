"""Pydantic DTOs for the Shoots endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ShootStatus

ALLOWED_CALL_SHEET_CONTENT_TYPES = frozenset({"application/pdf"})


class CreateShootBody(BaseModel):
    scheduled_at: datetime | None = None


class UpdateShootBody(BaseModel):
    """PATCH semantics — all optional."""

    scheduled_at: datetime | None = None


class ShootPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    scheduled_at: datetime | None
    call_sheet_object_name: str | None
    status: ShootStatus
    started_at: datetime | None
    wrapped_at: datetime | None
    created_at: datetime
    updated_at: datetime


class InitCallSheetUploadBody(BaseModel):
    content_type: str
    size_bytes: int = Field(gt=0, le=25 * 1024 * 1024)


class InitCallSheetUploadResponse(BaseModel):
    upload_session_url: str
    gcs_bucket: str
    gcs_object_name: str


class FinaliseCallSheetBody(BaseModel):
    gcs_bucket: str
    gcs_object_name: str


__all__ = [
    "ALLOWED_CALL_SHEET_CONTENT_TYPES",
    "CreateShootBody",
    "FinaliseCallSheetBody",
    "InitCallSheetUploadBody",
    "InitCallSheetUploadResponse",
    "ShootPublic",
    "UpdateShootBody",
]
