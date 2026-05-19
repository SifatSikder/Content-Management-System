"""Pydantic DTOs for the auth endpoints."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import Role


class RequestLinkBody(BaseModel):
    email: EmailStr
    locale: str | None = Field(default=None, max_length=8)


class RequestLinkResponse(BaseModel):
    """Anti-enumeration ack — identical for known and unknown emails."""

    status: str = "ok"


class UserPublic(BaseModel):
    """Fields safe to return to the authenticated user about themselves."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    name: str
    role: Role
    locale: str


class VerifyResponse(BaseModel):
    access_token: str
    user: UserPublic


__all__ = ["RequestLinkBody", "RequestLinkResponse", "UserPublic", "VerifyResponse"]
