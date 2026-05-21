"""Pydantic DTOs for the Locations + Location Photos endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# Phase-2 photo uploads accept jpeg/png/webp/heic — the camera capture path
# on mobile typically emits jpeg, the file-picker can emit any of these.
ALLOWED_PHOTO_CONTENT_TYPES = frozenset({"image/jpeg", "image/png", "image/webp", "image/heic"})


class CreateLocationBody(BaseModel):
    address: str = Field(min_length=1)
    latitude: float | None = None
    longitude: float | None = None
    contact_name: str | None = Field(default=None, max_length=120)
    contact_phone: str | None = Field(default=None, max_length=32)
    scheduled_at: datetime | None = None


class UpdateLocationBody(BaseModel):
    """PATCH semantics — all optional."""

    address: str | None = Field(default=None, min_length=1)
    latitude: float | None = None
    longitude: float | None = None
    contact_name: str | None = Field(default=None, max_length=120)
    contact_phone: str | None = Field(default=None, max_length=32)
    scheduled_at: datetime | None = None


class LocationPhotoPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    location_id: uuid.UUID
    gcs_bucket: str
    gcs_object_name: str
    content_type: str
    size_bytes: int | None
    created_at: datetime


class LocationPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    address: str
    latitude: float | None
    longitude: float | None
    contact_name: str | None
    contact_phone: str | None
    scheduled_at: datetime | None
    confirmed: bool
    photos: list[LocationPhotoPublic]
    created_at: datetime
    updated_at: datetime


class InitPhotoUploadBody(BaseModel):
    content_type: str
    size_bytes: int = Field(gt=0, le=25 * 1024 * 1024)  # 25 MB cap on a single photo


class InitPhotoUploadResponse(BaseModel):
    upload_session_url: str
    gcs_bucket: str
    gcs_object_name: str


class FinalisePhotoBody(BaseModel):
    gcs_bucket: str
    gcs_object_name: str
    content_type: str
    size_bytes: int = Field(gt=0)


__all__ = [
    "ALLOWED_PHOTO_CONTENT_TYPES",
    "CreateLocationBody",
    "FinalisePhotoBody",
    "InitPhotoUploadBody",
    "InitPhotoUploadResponse",
    "LocationPhotoPublic",
    "LocationPublic",
    "UpdateLocationBody",
]
