"""Per-department role endpoints (list / add / rename / delete)."""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, HTTPException, status

from app.auth.dependencies import CurrentUser, SessionDep
from app.schemas.department import (
    CreateRoleBody,
    RoleListResponse,
    RolePublic,
    UpdateRoleBody,
)
from app.services import department_service

router = APIRouter(prefix="/departments", tags=["department-roles"])
log = structlog.get_logger(__name__)


@router.get(
    "/{department_id}/roles",
    response_model=RoleListResponse,
    summary="List roles in a department",
)
async def get_roles(
    department_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> RoleListResponse:
    try:
        await department_service.get_department(session, department_id=department_id)
    except department_service.DepartmentNotFoundError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Department not found"
        ) from exc
    rows = await department_service.list_roles(session, department_id=department_id)
    return RoleListResponse(items=[RolePublic.model_validate(r) for r in rows])


@router.post(
    "/{department_id}/roles",
    response_model=RolePublic,
    status_code=status.HTTP_201_CREATED,
    summary="Add a role",
)
async def post_role(
    department_id: uuid.UUID,
    body: CreateRoleBody,
    user: CurrentUser,
    session: SessionDep,
) -> RolePublic:
    try:
        department = await department_service.get_department(
            session, department_id=department_id
        )
    except department_service.DepartmentNotFoundError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Department not found"
        ) from exc
    role = await department_service.create_role(
        session,
        department=department,
        key=body.key,
        name_i18n=body.name_i18n,
        description=body.description,
    )
    await session.commit()
    await session.refresh(role)
    return RolePublic.model_validate(role)


@router.patch(
    "/{department_id}/roles/{role_id}",
    response_model=RolePublic,
    summary="Rename / update a role",
)
async def patch_role(
    department_id: uuid.UUID,
    role_id: uuid.UUID,
    body: UpdateRoleBody,
    user: CurrentUser,
    session: SessionDep,
) -> RolePublic:
    try:
        role = await department_service.get_role(session, role_id=role_id)
    except department_service.RoleNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Role not found") from exc
    if role.department_id != department_id:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Role not in this department"
        )
    await department_service.update_role(
        session,
        role=role,
        name_i18n=body.name_i18n,
        description=body.description,
    )
    await session.commit()
    await session.refresh(role)
    return RolePublic.model_validate(role)


@router.delete(
    "/{department_id}/roles/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a role",
)
async def delete_role(
    department_id: uuid.UUID,
    role_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> None:
    try:
        role = await department_service.get_role(session, role_id=role_id)
    except department_service.RoleNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Role not found") from exc
    if role.department_id != department_id:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Role not in this department"
        )
    try:
        await department_service.delete_role(session, role=role)
    except department_service.RoleInUseError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Cannot delete role: {exc.member_count} member(s) still assigned. "
            "Reassign them to another role first.",
        ) from exc
    await session.commit()
