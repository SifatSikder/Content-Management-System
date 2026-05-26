"""Per-stage assignment endpoints — list / add / remove people on a card."""

from __future__ import annotations

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import (
    CurrentUser,
    ProjectAccess,
    SessionDep,
    require_project_access,
)
from app.models.project import ProjectModel
from app.models.user import UserModel
from app.schemas.project_assignment import (
    AddAssignmentBody,
    AssignmentListResponse,
    AssignmentPublic,
)
from app.services import assignment_service

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/projects/{project_id}", tags=["project-assignments"])


@router.get(
    "/stages/{stage_key}/assignees",
    response_model=AssignmentListResponse,
    summary="List active assignees for a stage on this project",
)
async def get_stage_assignees(
    project: Annotated[
        ProjectModel, Depends(require_project_access(ProjectAccess.VIEW))
    ],
    stage_key: str,
    session: SessionDep,
) -> AssignmentListResponse:
    rows = await assignment_service.list_active(
        session, project_id=project.id, stage_key=stage_key
    )
    return AssignmentListResponse(
        items=[AssignmentPublic.model_validate(r) for r in rows]
    )


@router.get(
    "/assignees",
    response_model=AssignmentListResponse,
    summary="List active assignees across every stage on this project",
)
async def get_all_assignees(
    project: Annotated[
        ProjectModel, Depends(require_project_access(ProjectAccess.VIEW))
    ],
    session: SessionDep,
) -> AssignmentListResponse:
    rows = await assignment_service.list_active_for_project(
        session, project_id=project.id
    )
    return AssignmentListResponse(
        items=[AssignmentPublic.model_validate(r) for r in rows]
    )


@router.post(
    "/stages/{stage_key}/assignees",
    response_model=AssignmentPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Add an assignee to a stage on this project",
)
async def post_stage_assignee(
    project: Annotated[
        ProjectModel, Depends(require_project_access(ProjectAccess.EDIT))
    ],
    stage_key: str,
    body: AddAssignmentBody,
    user: CurrentUser,
    session: SessionDep,
) -> AssignmentPublic:
    # Validate the target user exists. Membership checks are handled by RLS +
    # the calling user's project.edit gate; we don't enforce "must be in the
    # same department" here so the Asst CEO can pull in a member from another
    # department of the same business if needed.
    target = await session.get(UserModel, body.user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    row = await assignment_service.add(
        session,
        project=project,
        stage_key=stage_key,
        user_id=body.user_id,
        actor=user,
    )
    await session.commit()
    await session.refresh(row, attribute_names=["user"])
    return AssignmentPublic.model_validate(row)


@router.delete(
    "/stages/{stage_key}/assignees/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove an assignee from a stage on this project",
)
async def delete_stage_assignee(
    project: Annotated[
        ProjectModel, Depends(require_project_access(ProjectAccess.EDIT))
    ],
    stage_key: str,
    user_id: uuid.UUID,
    session: SessionDep,
) -> None:
    try:
        await assignment_service.remove(
            session, project=project, stage_key=stage_key, user_id=user_id
        )
    except assignment_service.AssignmentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    await session.commit()


__all__ = ["router"]
