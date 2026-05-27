"""Pydantic DTOs for the Cast endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# Release forms are typically a signed PDF, or a photo of one.
ALLOWED_RELEASE_CONTENT_TYPES = frozenset(
    {"application/pdf", "image/jpeg", "image/png", "image/webp"}
)


class CreateCastMemberBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    role_description: str | None = None
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=32)
    # Phase C: discriminator + lead-only fields. Default `kind="cast"` keeps
    # the existing casting flow unchanged; lead-mode clients send "lead"
    # plus `source` + `notes` and ignore the cast-only release_form upload.
    kind: str = Field(default="cast", pattern=r"^(cast|lead)$", max_length=16)
    source: str | None = Field(default=None, max_length=120)
    notes: str | None = None


class UpdateCastMemberBody(BaseModel):
    """PATCH semantics — all optional."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    role_description: str | None = None
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=32)
    source: str | None = Field(default=None, max_length=120)
    notes: str | None = None


class CastMemberPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    role_description: str | None
    contact_email: str | None
    contact_phone: str | None
    release_form_object_name: str | None
    kind: str
    source: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class InitReleaseUploadBody(BaseModel):
    content_type: str
    size_bytes: int = Field(gt=0, le=25 * 1024 * 1024)


class InitReleaseUploadResponse(BaseModel):
    upload_session_url: str
    gcs_bucket: str
    gcs_object_name: str


class FinaliseReleaseBody(BaseModel):
    gcs_bucket: str
    gcs_object_name: str
    content_type: str
    size_bytes: int = Field(gt=0)


__all__ = [
    "ALLOWED_RELEASE_CONTENT_TYPES",
    "CastMemberPublic",
    "CreateCastMemberBody",
    "FinaliseReleaseBody",
    "InitReleaseUploadBody",
    "InitReleaseUploadResponse",
    "UpdateCastMemberBody",
]
