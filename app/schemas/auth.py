"""Pydantic DTOs for the auth endpoints.

Auth (login, set/change/reset password, accept invite) is owned by NextAuth
on the Next.js layer. This module only declares the public projection of a
user — used by `GET /auth/me` and exported to TypeScript via the OpenAPI
artifact.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict

from app.models.enums import Role


class UserPublic(BaseModel):
    """Fields safe to return to the authenticated user about themselves."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    name: str
    role: Role
    locale: str


__all__ = ["UserPublic"]
