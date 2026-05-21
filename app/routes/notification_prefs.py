"""User notification preferences endpoints (Phase 3 Task 3.5).

Two routes on `/me/notification-prefs`:
    GET   — return the calling user's toggles (creating defaults if absent)
    PATCH — update any subset of the toggles
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter

from app.auth.dependencies import CurrentUser, SessionDep
from app.schemas.notification_prefs import NotificationPrefsPatch, NotificationPrefsPublic
from app.services import notification_prefs_service

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/me/notification-prefs", tags=["notification-prefs"])


@router.get(
    "",
    response_model=NotificationPrefsPublic,
    summary="Return the calling user's notification preferences",
)
async def get_prefs(
    user: CurrentUser,
    session: SessionDep,
) -> NotificationPrefsPublic:
    row = await notification_prefs_service.get_or_create(session, user_id=user.id)
    await session.commit()
    return NotificationPrefsPublic.model_validate(row)


@router.patch(
    "",
    response_model=NotificationPrefsPublic,
    summary="Update any subset of the notification preference toggles",
)
async def patch_prefs(
    body: NotificationPrefsPatch,
    user: CurrentUser,
    session: SessionDep,
) -> NotificationPrefsPublic:
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    row = await notification_prefs_service.update_prefs(
        session, user_id=user.id, patch=patch
    )
    await session.commit()
    await session.refresh(row)
    return NotificationPrefsPublic.model_validate(row)


__all__ = ["router"]
