"""Per-department workflow stage endpoints (list / add / reorder / rename / delete)."""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, HTTPException, status

from app.auth.dependencies import CurrentUser, SessionDep
from app.models.department import DepartmentModel
from app.schemas.department import (
    CreateStageBody,
    StageListResponse,
    StagePublic,
    UpdateStageBody,
)
from app.services import department_service

router = APIRouter(prefix="/departments", tags=["department-stages"])
log = structlog.get_logger(__name__)


async def _load_department_or_404(
    session: SessionDep, department_id: uuid.UUID
) -> DepartmentModel:
    try:
        return await department_service.get_department(
            session, department_id=department_id
        )
    except department_service.DepartmentNotFoundError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Department not found"
        ) from exc


@router.get(
    "/{department_id}/stages",
    response_model=StageListResponse,
    summary="List stages in a department",
)
async def get_stages(
    department_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> StageListResponse:
    await _load_department_or_404(session, department_id)
    rows = await department_service.list_stages(session, department_id=department_id)
    return StageListResponse(items=[StagePublic.model_validate(r) for r in rows])


@router.post(
    "/{department_id}/stages",
    response_model=StagePublic,
    status_code=status.HTTP_201_CREATED,
    summary="Add a stage",
)
async def post_stage(
    department_id: uuid.UUID,
    body: CreateStageBody,
    user: CurrentUser,
    session: SessionDep,
) -> StagePublic:
    department = await _load_department_or_404(session, department_id)
    stage = await department_service.create_stage(
        session,
        department=department,
        key=body.key,
        name_i18n=body.name_i18n,
        order_index=body.order_index,
        is_terminal=body.is_terminal,
        color=body.color,
        allowed_from_stage_ids=body.allowed_from_stage_ids,
    )
    await session.commit()
    await session.refresh(stage)
    return StagePublic.model_validate(stage)


@router.patch(
    "/{department_id}/stages/{stage_id}",
    response_model=StagePublic,
    summary="Rename / reorder / update a stage",
)
async def patch_stage(
    department_id: uuid.UUID,
    stage_id: uuid.UUID,
    body: UpdateStageBody,
    user: CurrentUser,
    session: SessionDep,
) -> StagePublic:
    try:
        stage = await department_service.get_stage(session, stage_id=stage_id)
    except department_service.StageNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Stage not found") from exc
    if stage.department_id != department_id:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Stage not in this department"
        )
    await department_service.update_stage(
        session,
        stage=stage,
        name_i18n=body.name_i18n,
        order_index=body.order_index,
        is_terminal=body.is_terminal,
        color=body.color,
        allowed_from_stage_ids=body.allowed_from_stage_ids,
    )
    await session.commit()
    await session.refresh(stage)
    return StagePublic.model_validate(stage)


@router.delete(
    "/{department_id}/stages/{stage_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a stage (refuses if any project references it)",
)
async def delete_stage(
    department_id: uuid.UUID,
    stage_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> None:
    try:
        stage = await department_service.get_stage(session, stage_id=stage_id)
    except department_service.StageNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Stage not found") from exc
    if stage.department_id != department_id:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Stage not in this department"
        )
    try:
        await department_service.delete_stage(session, stage=stage)
    except department_service.StageInUseError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Stage is referenced by one or more projects",
        ) from exc
    await session.commit()
