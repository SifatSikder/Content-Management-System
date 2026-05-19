"""Pydantic DTOs for the edit-upload endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import EditStatus

ALLOWED_CONTENT_TYPES: frozenset[str] = frozenset({"video/mp4", "video/quicktime"})
MAX_EDIT_SIZE_BYTES: int = 2 * 1024 * 1024 * 1024  # 2 GB


class InitUploadBody(BaseModel):
    content_type: str = Field(min_length=1, max_length=64)
    size_bytes: int = Field(gt=0, le=MAX_EDIT_SIZE_BYTES)
    filename: str | None = Field(default=None, max_length=255)


class InitUploadResponse(BaseModel):
    upload_session_url: str
    gcs_bucket: str
    gcs_object_name: str
    chunk_size_bytes: int = 8 * 1024 * 1024  # recommended client chunk size


class CreateEditBody(BaseModel):
    """Finalise the upload: ties the GCS object to a new EditVersionModel row."""

    gcs_bucket: str = Field(min_length=1, max_length=128)
    gcs_object_name: str = Field(min_length=1, max_length=512)
    content_type: str = Field(min_length=1, max_length=64)
    size_bytes: int = Field(gt=0, le=MAX_EDIT_SIZE_BYTES)
    notes: str | None = None
    # Comment ids resolved in this version (V1 → V2 checklist).
    resolved_comments: list[uuid.UUID] = Field(default_factory=list)


class RequestChangesBody(BaseModel):
    notes: str = Field(min_length=1)


class EditVersionPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    version_number: int
    uploader_id: uuid.UUID
    gcs_bucket: str
    gcs_object_name: str
    content_type: str
    size_bytes: int
    status: EditStatus
    notes: str | None
    approved_at: datetime | None
    approved_by: uuid.UUID | None
    resolved_comments: list[str]
    created_at: datetime
    updated_at: datetime


class PlaybackUrlResponse(BaseModel):
    url: str
    expires_in_seconds: int


class CreateEditCommentBody(BaseModel):
    body: str = Field(min_length=1)
    timestamp_seconds: float = Field(ge=0.0)


class EditCommentPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    edit_version_id: uuid.UUID
    author_id: uuid.UUID
    timestamp_seconds: float
    body: str
    resolved_at: datetime | None
    resolved_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


__all__ = [
    "ALLOWED_CONTENT_TYPES",
    "MAX_EDIT_SIZE_BYTES",
    "CreateEditBody",
    "CreateEditCommentBody",
    "EditCommentPublic",
    "EditVersionPublic",
    "InitUploadBody",
    "InitUploadResponse",
    "PlaybackUrlResponse",
    "RequestChangesBody",
]
