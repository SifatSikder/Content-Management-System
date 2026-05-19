"""Pydantic DTOs for script-related endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CreateVersionBody(BaseModel):
    body_markdown: str = Field(min_length=1)


class VersionPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    script_id: uuid.UUID
    version_number: int
    body_markdown: str
    author_id: uuid.UUID
    submitted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CreateCommentBody(BaseModel):
    body: str = Field(min_length=1)
    paragraph_anchor: str | None = Field(default=None, max_length=64)


class CommentPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version_id: uuid.UUID
    author_id: uuid.UUID
    body: str
    paragraph_anchor: str | None
    resolved_at: datetime | None
    resolved_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


__all__ = [
    "CommentPublic",
    "CreateCommentBody",
    "CreateVersionBody",
    "VersionPublic",
]
