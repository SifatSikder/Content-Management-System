"""Pydantic DTOs for the draft-idea endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.idea_version import SignoffDecision


class IdeaVersionPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    idea_id: uuid.UUID
    version_number: int
    body_markdown: str
    author_id: uuid.UUID
    submitted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CreateIdeaVersionBody(BaseModel):
    body_markdown: str = Field(min_length=1)


class IdeaSignoffPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    idea_version_id: uuid.UUID
    reviewer_id: uuid.UUID
    decision: SignoffDecision
    comment: str | None
    created_at: datetime


class CreateIdeaSignoffBody(BaseModel):
    decision: SignoffDecision
    comment: str | None = None


class IdeaSummaryPublic(BaseModel):
    """Per-project idea state — used by the IdeaTab to render the lock
    button + reviewer roster."""

    locked_at: datetime | None
    locked_by: uuid.UUID | None
    latest_version: IdeaVersionPublic | None
    latest_version_signoffs: list[IdeaSignoffPublic] = Field(default_factory=list)
    # Active assignees on draft_idea that the lock gate is waiting on.
    pending_reviewer_ids: list[uuid.UUID] = Field(default_factory=list)
    can_lock: bool
