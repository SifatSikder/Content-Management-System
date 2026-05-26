"""Pydantic DTOs for the raw-cut submission endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.project import OwnerPublic

# Raw cuts are commonly large (whole-shoot dailies). Same 2 GB cap as
# polished edits — we'll bump this when production storage settles.
ALLOWED_RAW_CUT_CONTENT_TYPES: frozenset[str] = frozenset({
    "video/mp4",
    "video/quicktime",
    "video/x-msvideo",
    "application/octet-stream",
})
MAX_RAW_CUT_SIZE_BYTES: int = 5 * 1024 * 1024 * 1024  # 5 GB


class InitRawCutUploadBody(BaseModel):
    content_type: str = Field(min_length=1, max_length=64)
    size_bytes: int = Field(gt=0, le=MAX_RAW_CUT_SIZE_BYTES)
    filename: str | None = Field(default=None, max_length=255)


class InitRawCutUploadResponse(BaseModel):
    upload_session_url: str
    gcs_bucket: str
    gcs_object_name: str
    chunk_size_bytes: int = 8 * 1024 * 1024


class FinaliseRawCutBody(BaseModel):
    gcs_bucket: str = Field(min_length=1, max_length=128)
    gcs_object_name: str = Field(min_length=1, max_length=512)
    content_type: str | None = Field(default=None, max_length=64)
    size_bytes: int | None = Field(default=None, gt=0, le=MAX_RAW_CUT_SIZE_BYTES)
    original_filename: str | None = Field(default=None, max_length=255)


class RawCutPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    uploader_id: uuid.UUID
    uploader: OwnerPublic
    gcs_bucket: str
    gcs_object_name: str
    original_filename: str | None
    content_type: str | None
    byte_size: int | None
    submitted_at: datetime
