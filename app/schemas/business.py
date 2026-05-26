"""Pydantic DTOs for businesses, business memberships, and the `/me`
business-context endpoints (Phase A)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import BusinessMembershipStatus
from app.schemas.auth import UserPublic


class CreateBusinessBody(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        pattern=r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$",
    )


class UpdateBusinessBody(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        pattern=r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$",
    )


class BusinessPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    owner_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    # Short-lived signed GCS URL minted on response. None when no logo is
    # uploaded. Re-fetch the parent resource when this expires (~15 min).
    logo_url: str | None = None


class BusinessListResponse(BaseModel):
    items: list[BusinessPublic]


class InitLogoUploadBody(BaseModel):
    content_type: str = Field(min_length=1, max_length=100)
    size_bytes: int = Field(ge=1)


class InitLogoUploadResponse(BaseModel):
    upload_session_url: str
    gcs_bucket: str
    gcs_object_name: str


class FinaliseLogoBody(BaseModel):
    gcs_object_name: str = Field(min_length=1, max_length=512)


class InviteBusinessMemberBody(BaseModel):
    email: EmailStr


class BusinessMembershipPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    business_id: uuid.UUID
    user_id: uuid.UUID
    user: UserPublic
    status: BusinessMembershipStatus
    invited_by: uuid.UUID | None = None
    joined_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class BusinessMembershipListResponse(BaseModel):
    items: list[BusinessMembershipPublic]


class UpdateBusinessMembershipBody(BaseModel):
    """Body for `PATCH /businesses/{id}/memberships/{id}`.

    Flips a member between active (full access) and revoked (soft-disabled
    — kept in the DB with all role assignments intact, but blocked from
    accessing the business). The `invited` status is reserved for legacy
    rows and not accepted as an input here.
    """

    status: BusinessMembershipStatus


class MeBusinessEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    is_owner: bool
    membership_status: BusinessMembershipStatus | None = None
    logo_url: str | None = None


class MeBusinessesResponse(BaseModel):
    items: list[MeBusinessEntry]


__all__ = [
    "BusinessListResponse",
    "BusinessMembershipListResponse",
    "BusinessMembershipPublic",
    "BusinessPublic",
    "CreateBusinessBody",
    "FinaliseLogoBody",
    "InitLogoUploadBody",
    "InitLogoUploadResponse",
    "InviteBusinessMemberBody",
    "MeBusinessEntry",
    "MeBusinessesResponse",
    "UpdateBusinessBody",
    "UpdateBusinessMembershipBody",
]
