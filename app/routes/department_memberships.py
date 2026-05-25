"""Department membership endpoints — assign a user a role inside a department."""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, HTTPException, status

from app.auth.dependencies import CurrentUser, SessionDep
from app.schemas.department import (
    AssignDepartmentMemberBody,
    DepartmentMembershipListResponse,
    DepartmentMembershipPublic,
)
from app.services import department_service

router = APIRouter(prefix="/departments", tags=["department-memberships"])
log = structlog.get_logger(__name__)


@router.get(
    "/{department_id}/memberships",
    response_model=DepartmentMembershipListResponse,
    summary="List department memberships",
)
async def get_memberships(
    department_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> DepartmentMembershipListResponse:
    try:
        await department_service.get_department(session, department_id=department_id)
    except department_service.DepartmentNotFoundError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Department not found"
        ) from exc
    rows = await department_service.list_department_memberships(
        session, department_id=department_id
    )
    return DepartmentMembershipListResponse(
        items=[DepartmentMembershipPublic.model_validate(r) for r in rows]
    )


@router.post(
    "/{department_id}/memberships",
    response_model=DepartmentMembershipPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Assign a user a role inside this department",
)
async def post_membership(
    department_id: uuid.UUID,
    body: AssignDepartmentMemberBody,
    user: CurrentUser,
    session: SessionDep,
) -> DepartmentMembershipPublic:
    try:
        department = await department_service.get_department(
            session, department_id=department_id
        )
    except department_service.DepartmentNotFoundError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Department not found"
        ) from exc
    membership = await department_service.assign_department_member(
        session,
        department=department,
        user_id=body.user_id,
        role_id=body.role_id,
    )
    await session.commit()
    # `lazy="raise"` on the user/role relations means a vanilla refresh
    # would explode when serialisation walks them. Load them explicitly.
    await session.refresh(membership, attribute_names=["user", "role"])
    return DepartmentMembershipPublic.model_validate(membership)


@router.delete(
    "/{department_id}/memberships/{membership_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a user from a department",
)
async def delete_membership(
    department_id: uuid.UUID,
    membership_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> None:
    try:
        await department_service.remove_department_member(
            session,
            membership_id=membership_id,
            department_id=department_id,
        )
    except department_service.DepartmentNotFoundError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Membership not found"
        ) from exc
    await session.commit()
