"""Pydantic DTOs for script-related endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.script import ScriptSignoffDecision


class CreateVersionBody(BaseModel):
    body_markdown: str = Field(min_length=1)


class UpdateVersionBody(BaseModel):
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


class ScriptSignoffPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    script_version_id: uuid.UUID
    reviewer_id: uuid.UUID
    # Snapshot of the reviewer at the time of read — saves the UI from
    # joining against department memberships (which a global super-admin
    # may not have rows in). Populated by `get_signoffs`; left null by
    # endpoints that don't bother joining.
    reviewer_name: str | None = None
    reviewer_avatar_url: str | None = None
    decision: ScriptSignoffDecision
    comment: str | None
    created_at: datetime


class CreateSignoffBody(BaseModel):
    decision: ScriptSignoffDecision
    comment: str | None = None


class ScriptSummaryPublic(BaseModel):
    """Per-project script-phase state — used by the ScriptTab to render
    the lock button + reviewer roster. Mirrors `IdeaSummaryPublic`."""

    locked_at: datetime | None
    locked_by: uuid.UUID | None
    latest_version: VersionPublic | None
    latest_version_signoffs: list[ScriptSignoffPublic] = Field(default_factory=list)
    pending_reviewer_ids: list[uuid.UUID] = Field(default_factory=list)
    can_lock: bool
    reviewer_count: int = 0


__all__ = [
    "CommentPublic",
    "CreateCommentBody",
    "CreateSignoffBody",
    "CreateVersionBody",
    "ScriptSignoffPublic",
    "ScriptSummaryPublic",
    "UpdateVersionBody",
    "VersionPublic",
]
