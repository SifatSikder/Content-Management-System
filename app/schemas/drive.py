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


class DriveDocumentPublic(BaseModel):
    """One row in the Drive picker — what the script-import dialog renders.

    `web_view_link` is the user-facing URL (clickable to inspect the source
    doc in Drive). `id` is what we hand back to
    `GET /drive/documents/{id}/content` to fetch the rendered HTML body.
    """

    id: str
    name: str
    modified_time: datetime | None = None
    web_view_link: str | None = None


class DriveDocumentListResponse(BaseModel):
    items: list[DriveDocumentPublic]


class DriveDocumentContent(BaseModel):
    """Rendered body of a single Google Doc — fetch-only, no persistence.

    Returned by `GET /drive/documents/{id}/content`. The script-import flow
    loads this into the editor as an unsaved draft; persistence happens via
    the normal `POST /projects/{id}/scripts` createVersion endpoint when
    the user clicks "Save new version".
    """

    body: str


__all__ = [
    "AttachDriveBody",
    "DriveConnectionPublic",
    "DriveDocumentContent",
    "DriveDocumentListResponse",
    "DriveDocumentPublic",
    "StartConnectResponse",
]
