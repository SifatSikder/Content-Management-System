"""Project endpoints.

All routes are JWT-authenticated. Mutation routes are role/access-gated using
`app.auth.dependencies`. Stage moves additionally check `can_user_move_to_stage`.
"""

from __future__ import annotations

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.dependencies import (
    CurrentUser,
    ProjectAccess,
    SessionDep,
    can_user_move_to_stage,
    require_project_access,
    require_role,
)
from app.models.enums import PipelineStage, Role
from app.models.project import ProjectModel
from app.schemas.activity import ActivityListResponse, ActivityPublic
from app.schemas.project import (
    CreateProjectBody,
    MoveStageBody,
    ProjectListResponse,
    ProjectPublic,
    UpdateProjectBody,
)
from app.services import activity_service, project_service
from app.services.activity_service import (
    DEFAULT_ACTIVITY_PAGE_SIZE,
    MAX_ACTIVITY_PAGE_SIZE,
    InvalidActivityCursorError,
)
from app.services.project_service import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    InvalidCursorError,
    ListFilters,
)

router = APIRouter(prefix="/projects", tags=["projects"])
log = structlog.get_logger(__name__)

CreatorRoles = require_role(Role.CEO, Role.ASSISTANT_DIRECTOR, Role.JUNIOR_DIRECTOR)
AdminRoles = require_role(Role.CEO, Role.ASSISTANT_DIRECTOR)


@router.post(
    "",
    response_model=ProjectPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Create a project",
)
async def post_project(
    body: CreateProjectBody,
    user: Annotated[CurrentUser, Depends(CreatorRoles)],
    session: SessionDep,
) -> ProjectPublic:
    project = await project_service.create_project(
        session,
        actor=user,
        title=body.title,
        category=body.category,
        description=body.description,
        due_date=body.due_date,
        owner_id_override=body.owner_id,
    )
    await session.commit()
    await session.refresh(project)
    return ProjectPublic.model_validate(project)


@router.get("", response_model=ProjectListResponse, summary="List projects")
async def get_projects(
    user: CurrentUser,
    session: SessionDep,
    stage: PipelineStage | None = None,
    owner_id: uuid.UUID | None = None,
    filter: Annotated[str | None, Query(pattern="^mine$")] = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
) -> ProjectListResponse:
    try:
        items, next_cursor = await project_service.list_projects(
            session,
            user=user,
            filters=ListFilters(stage=stage, owner_id=owner_id, mine=filter == "mine"),
            cursor=cursor,
            limit=limit,
        )
    except InvalidCursorError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    return ProjectListResponse(
        items=[ProjectPublic.model_validate(item) for item in items],
        next_cursor=next_cursor,
    )


@router.get("/{project_id}", response_model=ProjectPublic, summary="Get one project")
async def get_project(
    project: Annotated[ProjectModel, Depends(require_project_access(ProjectAccess.VIEW))],
) -> ProjectPublic:
    return ProjectPublic.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectPublic, summary="Update a project")
async def patch_project(
    body: UpdateProjectBody,
    project: Annotated[ProjectModel, Depends(require_project_access(ProjectAccess.EDIT))],
    user: CurrentUser,
    session: SessionDep,
) -> ProjectPublic:
    await project_service.update_project(
        session,
        actor=user,
        project=project,
        title=body.title,
        description=body.description,
        category=body.category,
        due_date=body.due_date,
    )
    await session.commit()
    await session.refresh(project)
    return ProjectPublic.model_validate(project)


@router.post(
    "/{project_id}/stage",
    response_model=ProjectPublic,
    summary="Advance a project's pipeline stage",
)
async def post_project_stage(
    body: MoveStageBody,
    project: Annotated[ProjectModel, Depends(require_project_access(ProjectAccess.VIEW))],
    user: CurrentUser,
    session: SessionDep,
) -> ProjectPublic:
    if not can_user_move_to_stage(user, project, body.stage):
        log.warning(
            "stage_move_denied",
            user_id=str(user.id),
            user_role=user.role.value,
            project_id=str(project.id),
            target_stage=body.stage.value,
        )
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to move to that stage")

    await project_service.move_stage(
        session, actor=user, project=project, target_stage=body.stage
    )
    await session.commit()
    await session.refresh(project)
    return ProjectPublic.model_validate(project)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a project (30-day window)",
)
async def delete_project(
    project: Annotated[ProjectModel, Depends(require_project_access(ProjectAccess.MANAGE))],
    user: CurrentUser,
    session: SessionDep,
) -> None:
    await project_service.soft_delete(session, actor=user, project=project)
    await session.commit()


@router.get(
    "/{project_id}/activity",
    response_model=ActivityListResponse,
    summary="Activity feed for a project (paginated, most-recent first)",
)
async def get_activity(
    project: Annotated[ProjectModel, Depends(require_project_access(ProjectAccess.VIEW))],
    session: SessionDep,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_ACTIVITY_PAGE_SIZE)] = DEFAULT_ACTIVITY_PAGE_SIZE,
) -> ActivityListResponse:
    try:
        items, next_cursor = await activity_service.list_for_project(
            session, project_id=project.id, cursor=cursor, limit=limit
        )
    except InvalidActivityCursorError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return ActivityListResponse(
        items=[ActivityPublic.model_validate(i) for i in items],
        next_cursor=next_cursor,
    )


@router.post(
    "/{project_id}/restore",
    response_model=ProjectPublic,
    summary="Restore a soft-deleted project",
)
async def post_project_restore(
    project_id: uuid.UUID,
    user: Annotated[CurrentUser, Depends(AdminRoles)],
    session: SessionDep,
) -> ProjectPublic:
    # Bypass the "no deleted" filter — we want to restore a deleted row.
    try:
        project = await project_service.get_project(
            session, project_id=project_id, include_deleted=True
        )
    except project_service.ProjectNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found") from exc

    await project_service.restore(session, actor=user, project=project)
    await session.commit()
    await session.refresh(project)
    return ProjectPublic.model_validate(project)
