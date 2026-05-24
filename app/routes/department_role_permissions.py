"""Per-role permission matrix endpoints.

`PATCH` upserts a single `(role, action_key) -> allowed` row. `GET` lists
every flipped permission for a role.
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, HTTPException, status

from app.auth.dependencies import CurrentUser, SessionDep
from app.schemas.department import (
    PermissionListResponse,
    PermissionPublic,
    UpsertPermissionBody,
)
from app.services import department_service

router = APIRouter(prefix="/department-roles", tags=["department-permissions"])
log = structlog.get_logger(__name__)


@router.get(
    "/{role_id}/permissions",
    response_model=PermissionListResponse,
    summary="List permission flags for a role",
)
async def get_permissions(
    role_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> PermissionListResponse:
    try:
        await department_service.get_role(session, role_id=role_id)
    except department_service.RoleNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Role not found") from exc
    rows = await department_service.list_permissions(
        session, department_role_id=role_id
    )
    return PermissionListResponse(
        items=[PermissionPublic.model_validate(r) for r in rows]
    )


@router.patch(
    "/{role_id}/permissions",
    response_model=PermissionPublic,
    summary="Upsert a single (action_key, allowed) flag",
)
async def patch_permission(
    role_id: uuid.UUID,
    body: UpsertPermissionBody,
    user: CurrentUser,
    session: SessionDep,
) -> PermissionPublic:
    try:
        role = await department_service.get_role(session, role_id=role_id)
    except department_service.RoleNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Role not found") from exc
    perm = await department_service.upsert_permission(
        session, role=role, action_key=body.action_key, allowed=body.allowed
    )
    await session.commit()
    await session.refresh(perm)
    return PermissionPublic.model_validate(perm)
