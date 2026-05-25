"""User notification preference endpoints (Phase B — department-scoped).

Two routes mounted under `/me/notification-prefs`:

    GET ?department_id=…  — list every event in the department with the
                            user's effective `enabled` value
    PATCH                 — set one `(department_id, event_key)` toggle

The GET response is what the frontend settings page renders. The PATCH
body carries one toggle at a time; the frontend issues one PATCH per
flipped checkbox.
"""

from __future__ import annotations

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.auth.dependencies import CurrentUser, SessionDep
from app.models.department import DepartmentModel
from app.models.department_event_definition import DepartmentEventDefinitionModel
from app.schemas.notification_prefs import (
    DepartmentPrefsPublic,
    EventPrefPublic,
    SetEventPrefBody,
)
from app.services import notification_prefs_service

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/me/notification-prefs", tags=["notification-prefs"])


@router.get(
    "",
    response_model=DepartmentPrefsPublic,
    summary="Per-event notification toggles for the current user in a department",
)
async def get_prefs(
    user: CurrentUser,
    session: SessionDep,
    department_id: Annotated[uuid.UUID, Query(...)],
) -> DepartmentPrefsPublic:
    # Make sure the umbrella row exists so future cross-department prefs
    # have a target. Per-event overrides land in user_notification_pref_events.
    await notification_prefs_service.get_or_create(session, user_id=user.id)
    rows = await notification_prefs_service.list_for_department(
        session, user_id=user.id, department_id=department_id
    )
    await session.commit()
    return DepartmentPrefsPublic(
        department_id=department_id,
        events=[EventPrefPublic(**row) for row in rows],
    )


@router.patch(
    "",
    response_model=DepartmentPrefsPublic,
    summary="Toggle one (department, event) notification preference",
)
async def patch_prefs(
    body: SetEventPrefBody,
    user: CurrentUser,
    session: SessionDep,
) -> DepartmentPrefsPublic:
    # Look up the department to grab its business_id for the new override row.
    dept = await session.get(DepartmentModel, body.department_id)
    if dept is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Department not found")

    # Validate the event exists in this department.
    event_exists = await session.execute(
        select(DepartmentEventDefinitionModel.id).where(
            DepartmentEventDefinitionModel.department_id == body.department_id,
            DepartmentEventDefinitionModel.event_key == body.event_key,
        )
    )
    if event_exists.first() is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Event '{body.event_key}' not defined for this department",
        )

    await notification_prefs_service.set_pref(
        session,
        user_id=user.id,
        department_id=body.department_id,
        business_id=dept.business_id,
        event_key=body.event_key,
        enabled=body.enabled,
    )
    rows = await notification_prefs_service.list_for_department(
        session, user_id=user.id, department_id=body.department_id
    )
    await session.commit()
    return DepartmentPrefsPublic(
        department_id=body.department_id,
        events=[EventPrefPublic(**row) for row in rows],
    )


__all__ = ["router"]
