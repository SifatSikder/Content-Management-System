"""DTOs for /me/notification-prefs (Phase 3 Task 3.5)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class NotificationPrefsPublic(BaseModel):
    """All boolean toggles for the calling user. Defaults are all `True`."""

    model_config = ConfigDict(from_attributes=True)

    push_project_created: bool
    push_script_submitted: bool
    push_script_locked: bool
    push_cut_uploaded: bool
    push_cut_comment: bool
    push_cut_approved: bool
    push_cut_changes_requested: bool
    push_project_published: bool
    push_project_stuck: bool


class NotificationPrefsPatch(BaseModel):
    """PATCH body — every field optional; only included ones are updated."""

    push_project_created: bool | None = None
    push_script_submitted: bool | None = None
    push_script_locked: bool | None = None
    push_cut_uploaded: bool | None = None
    push_cut_comment: bool | None = None
    push_cut_approved: bool | None = None
    push_cut_changes_requested: bool | None = None
    push_project_published: bool | None = None
    push_project_stuck: bool | None = None


__all__ = ["NotificationPrefsPatch", "NotificationPrefsPublic"]
