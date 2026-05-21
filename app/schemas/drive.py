"""Pydantic DTOs for the Google Drive endpoints (Phase 3 Task 3.3)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DriveConnectionPublic(BaseModel):
    """What `/auth/google/drive/me` returns. Never includes the refresh token."""

    model_config = ConfigDict(from_attributes=True)

    google_email: str
    scopes: str
    connected_at: datetime


class StartConnectResponse(BaseModel):
    """Returned by /auth/google/drive/start — frontend redirects to `url`."""

    url: str


class AttachDriveBody(BaseModel):
    folder_id: str = Field(min_length=1, max_length=128)
    folder_url: str | None = Field(default=None, max_length=2048)


class ImportGdocBody(BaseModel):
    """Either a Google Docs URL or a bare document ID is accepted."""

    document: str = Field(min_length=10, max_length=2048)


__all__ = [
    "AttachDriveBody",
    "DriveConnectionPublic",
    "ImportGdocBody",
    "StartConnectResponse",
]
