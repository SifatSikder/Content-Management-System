"""Per-department stage-handoff CRUD."""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app.auth.dependencies import CurrentUser, SessionDep
from app.models.department import DepartmentModel
from app.models.department_role import DepartmentRoleModel
from app.schemas.department_handoff import (
    StageHandoffListResponse,
    StageHandoffPublic,
    UpsertStageHandoffBody,
)
from app.services import handoff_service, permission_service

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/departments", tags=["department-handoffs"])


async def _load_department(
    session: SessionDep, department_id: uuid.UUID
) -> DepartmentModel:
    result = await session.execute(
        select(DepartmentModel).where(DepartmentModel.id == department_id)
    )
    department = result.scalar_one_or_none()
    if department is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Department not found")
    return department


async def _require_edit(
    session: SessionDep,
    user: CurrentUser,
    department: DepartmentModel,
    request: Request,
) -> None:
    allowed = await permission_service.can_user_perform_action(
        session,
        user=user,
        department_id=department.id,
        action_key="department.edit_handoffs",
        request=request,
    )
    if not allowed:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Insufficient permissions to edit stage handoffs",
        )


@router.get(
    "/{department_id}/stage-handoffs",
    response_model=StageHandoffListResponse,
    summary="List stage hand-off rules for this department",
)
async def get_stage_handoffs(
    department_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> StageHandoffListResponse:
    await _load_department(session, department_id)
    rows = await handoff_service.list_handoffs(
        session, department_id=department_id
    )
    return StageHandoffListResponse(
        items=[StageHandoffPublic.model_validate(r) for r in rows],
    )


@router.put(
    "/{department_id}/stage-handoffs",
    response_model=StageHandoffPublic,
    summary="Create or replace the hand-off rule for a stage",
)
async def put_stage_handoff(
    department_id: uuid.UUID,
    body: UpsertStageHandoffBody,
    user: CurrentUser,
    session: SessionDep,
    request: Request,
) -> StageHandoffPublic:
    department = await _load_department(session, department_id)
    await _require_edit(session, user, department, request)

    # Validate every role belongs to this department.
    if body.role_ids:
        roles = await session.execute(
            select(DepartmentRoleModel.id).where(
                DepartmentRoleModel.id.in_(body.role_ids),
                DepartmentRoleModel.department_id == department_id,
            )
        )
        valid_ids = {row[0] for row in roles.all()}
        bad = [str(r) for r in body.role_ids if r not in valid_ids]
        if bad:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"role_ids do not belong to this department: {bad}",
            )

    row = await handoff_service.upsert_handoff(
        session,
        business_id=department.business_id,
        department_id=department_id,
        stage_key=body.stage_key,
        role_ids=body.role_ids,
    )
    await session.commit()
    return StageHandoffPublic.model_validate(row)


__all__ = ["router"]
