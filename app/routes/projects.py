"""Project endpoints.

All routes are JWT-authenticated. Mutation routes are role/access-gated using
`app.auth.dependencies`. Stage moves additionally check
`permission_service.can_user_move_to_stage`.
"""

from __future__ import annotations

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select

from app.auth.dependencies import (
    CurrentUser,
    ProjectAccess,
    SessionDep,
    require_project_access,
    require_role,
)
from app.models.department import DepartmentModel
from app.models.department_stage import DepartmentStageModel
from app.models.enums import Role
from app.models.project import ProjectModel
from app.schemas.activity import ActivityListResponse, ActivityPublic
from app.schemas.project import (
    CreateProjectBody,
    MoveStageBody,
    ProjectListResponse,
    ProjectPublic,
    UpdateProjectBody,
)
from app.services import activity_service, permission_service, project_service
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
    StageNotFoundError,
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
    # The business context middleware already validates that the user has
    # access to this business; we still need to resolve the department's
    # business_id for the new project's denormalised business_id column.
    department = await session.get(DepartmentModel, body.department_id)
    if department is None or department.archived_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Department not found")

    try:
        project = await project_service.create_project(
            session,
            actor=user,
            title=body.title,
            category=body.category,
            business_id=department.business_id,
            department_id=department.id,
            description=body.description,
            due_date=body.due_date,
            owner_id_override=body.owner_id,
            stage_id=body.stage_id,
        )
    except StageNotFoundError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await session.commit()
    await session.refresh(project)
    return ProjectPublic.model_validate(project)


@router.get("", response_model=ProjectListResponse, summary="List projects")
async def get_projects(
    user: CurrentUser,
    session: SessionDep,
    stage: Annotated[str | None, Query(description="Stage key (e.g. 'idea')")] = None,
    owner_id: uuid.UUID | None = None,
    filter: Annotated[str | None, Query(pattern="^mine$")] = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
) -> ProjectListResponse:
    try:
        items, next_cursor = await project_service.list_projects(
            session,
            user=user,
            filters=ListFilters(stage_key=stage, owner_id=owner_id, mine=filter == "mine"),
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
    request: Request,
) -> ProjectPublic:
    target_stage_id = await _resolve_target_stage_id(session, project, body)
    if target_stage_id is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Unknown target stage for this department"
        )

    allowed = await permission_service.can_user_move_to_stage(
        session,
        user=user,
        project=project,
        target_stage_id=target_stage_id,
        request=request,
    )
    if not allowed:
        log.warning(
            "stage_move_denied",
            user_id=str(user.id),
            user_role=user.role.value,
            project_id=str(project.id),
            target_stage_id=str(target_stage_id),
        )
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to move to that stage")

    try:
        await project_service.move_stage(
            session, actor=user, project=project, target_stage_id=target_stage_id
        )
    except StageNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    await session.commit()
    await session.refresh(project)
    return ProjectPublic.model_validate(project)


async def _resolve_target_stage_id(
    session: SessionDep, project: ProjectModel, body: MoveStageBody
) -> uuid.UUID | None:
    """Resolve `MoveStageBody` to a concrete stage id inside the project's
    department.

      * If `stage_id` is set, validate it belongs to the department.
      * Else, resolve `stage_key` against the department's stages.
    """
    if body.stage_id is not None:
        result = await session.execute(
            select(DepartmentStageModel.id).where(
                DepartmentStageModel.id == body.stage_id,
                DepartmentStageModel.department_id == project.department_id,
            )
        )
        return result.scalar_one_or_none()
    if body.stage_key is not None:
        return await project_service.resolve_stage_id_by_key(
            session, department_id=project.department_id, key=body.stage_key
        )
    return None


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
