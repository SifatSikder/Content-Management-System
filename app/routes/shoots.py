"""Shoot endpoints + state machine + call-sheet upload."""

from __future__ import annotations

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.auth.dependencies import (
    CurrentUser,
    ProjectAccess,
    SessionDep,
    _user_can_access_project,
    require_project_access,
)
from app.config import get_settings
from app.models.enums import ShootStatus
from app.models.project import ProjectModel
from app.models.shoot import ShootModel
from app.schemas.shoot import (
    ALLOWED_CALL_SHEET_CONTENT_TYPES,
    CreateShootBody,
    FinaliseCallSheetBody,
    InitCallSheetUploadBody,
    InitCallSheetUploadResponse,
    ShootPublic,
    UpdateShootBody,
)
from app.services import shoot_service, storage_service
from app.services.shoot_service import (
    IllegalShootTransitionError,
    ShootNotFoundError,
)

log = structlog.get_logger(__name__)

projects_router = APIRouter(prefix="/projects/{project_id}/shoots", tags=["shoots"])
shoots_router = APIRouter(prefix="/shoots", tags=["shoots"])


def _call_sheet_object_name(project_id: uuid.UUID, shoot_id: uuid.UUID) -> str:
    return f"projects/{project_id}/shoots/{shoot_id}/call_sheet_{uuid.uuid4()}.pdf"


# ---------- collection ----------

@projects_router.post(
    "",
    response_model=ShootPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Schedule a shoot for a project",
)
async def post_shoot(
    body: CreateShootBody,
    project: Annotated[ProjectModel, Depends(require_project_access(ProjectAccess.EDIT))],
    user: CurrentUser,
    session: SessionDep,
) -> ShootPublic:
    shoot = await shoot_service.create_shoot(
        session,
        project=project,
        actor=user,
        scheduled_at=body.scheduled_at,
        gear_checklist=body.gear_checklist,
    )
    await session.commit()
    await session.refresh(shoot)
    return ShootPublic.model_validate(shoot)


@projects_router.get(
    "",
    response_model=list[ShootPublic],
    summary="List shoots for a project",
)
async def get_shoots(
    project: Annotated[ProjectModel, Depends(require_project_access(ProjectAccess.VIEW))],
    session: SessionDep,
) -> list[ShootPublic]:
    shoots = await shoot_service.list_shoots(session, project_id=project.id)
    return [ShootPublic.model_validate(s) for s in shoots]


# ---------- instance ----------

async def _project_for_shoot(session: SessionDep, shoot: ShootModel) -> ProjectModel:
    project_q = await session.execute(
        select(ProjectModel).where(
            ProjectModel.id == shoot.project_id,
            ProjectModel.deleted_at.is_(None),
        )
    )
    project = project_q.scalar_one_or_none()
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project


async def _load_shoot_and_project(
    session: SessionDep, shoot_id: uuid.UUID, user: CurrentUser, level: ProjectAccess
) -> tuple[ShootModel, ProjectModel]:
    try:
        shoot = await shoot_service.get_shoot(session, shoot_id=shoot_id)
    except ShootNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Shoot not found") from exc
    project = await _project_for_shoot(session, shoot)
    if not _user_can_access_project(user, project, level):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient project access")
    return shoot, project


@shoots_router.get(
    "/{shoot_id}", response_model=ShootPublic, summary="Get one shoot"
)
async def get_shoot(
    shoot_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> ShootPublic:
    shoot, _ = await _load_shoot_and_project(session, shoot_id, user, ProjectAccess.VIEW)
    return ShootPublic.model_validate(shoot)


@shoots_router.patch(
    "/{shoot_id}", response_model=ShootPublic, summary="Update a shoot"
)
async def patch_shoot(
    shoot_id: uuid.UUID,
    body: UpdateShootBody,
    user: CurrentUser,
    session: SessionDep,
) -> ShootPublic:
    shoot, _ = await _load_shoot_and_project(session, shoot_id, user, ProjectAccess.EDIT)
    await shoot_service.update_shoot(
        session,
        shoot=shoot,
        actor=user,
        scheduled_at=body.scheduled_at,
        gear_checklist=body.gear_checklist,
    )
    await session.commit()
    await session.refresh(shoot)
    return ShootPublic.model_validate(shoot)


@shoots_router.post(
    "/{shoot_id}/start",
    response_model=ShootPublic,
    summary="Transition a shoot to in_progress",
)
async def post_start_shoot(
    shoot_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> ShootPublic:
    shoot, project = await _load_shoot_and_project(
        session, shoot_id, user, ProjectAccess.EDIT
    )
    try:
        await shoot_service.transition_shoot(
            session, shoot=shoot, project=project, actor=user, target=ShootStatus.IN_PROGRESS
        )
    except IllegalShootTransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await session.commit()
    await session.refresh(shoot)
    return ShootPublic.model_validate(shoot)


@shoots_router.post(
    "/{shoot_id}/wrap",
    response_model=ShootPublic,
    summary="Wrap a shoot (advances project to SHOOT_DONE)",
)
async def post_wrap_shoot(
    shoot_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> ShootPublic:
    shoot, project = await _load_shoot_and_project(
        session, shoot_id, user, ProjectAccess.EDIT
    )
    try:
        await shoot_service.transition_shoot(
            session, shoot=shoot, project=project, actor=user, target=ShootStatus.WRAPPED
        )
    except IllegalShootTransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await session.commit()
    await session.refresh(shoot)
    return ShootPublic.model_validate(shoot)


@shoots_router.delete(
    "/{shoot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a shoot",
)
async def delete_shoot(
    shoot_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> None:
    shoot, _ = await _load_shoot_and_project(session, shoot_id, user, ProjectAccess.EDIT)
    await shoot_service.delete_shoot(session, shoot=shoot, actor=user)
    await session.commit()


# ---------- call-sheet upload ----------

@shoots_router.post(
    "/{shoot_id}/call-sheet/init-upload",
    response_model=InitCallSheetUploadResponse,
    summary="Mint a GCS resumable session for a call-sheet PDF",
)
async def post_init_call_sheet_upload(
    shoot_id: uuid.UUID,
    body: InitCallSheetUploadBody,
    user: CurrentUser,
    session: SessionDep,
) -> InitCallSheetUploadResponse:
    if body.content_type not in ALLOWED_CALL_SHEET_CONTENT_TYPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Content type {body.content_type!r} not allowed",
        )
    shoot, project = await _load_shoot_and_project(session, shoot_id, user, ProjectAccess.EDIT)
    settings = get_settings()
    bucket = settings.gcs_bucket_assets
    object_name = _call_sheet_object_name(project.id, shoot.id)
    session_url = await storage_service.create_resumable_upload_session(
        bucket_name=bucket,
        object_name=object_name,
        content_type=body.content_type,
        size_bytes=body.size_bytes,
    )
    return InitCallSheetUploadResponse(
        upload_session_url=session_url, gcs_bucket=bucket, gcs_object_name=object_name
    )


@shoots_router.post(
    "/{shoot_id}/call-sheet",
    response_model=ShootPublic,
    summary="Finalise a call-sheet upload",
)
async def post_finalise_call_sheet(
    shoot_id: uuid.UUID,
    body: FinaliseCallSheetBody,
    user: CurrentUser,
    session: SessionDep,
) -> ShootPublic:
    shoot, _ = await _load_shoot_and_project(session, shoot_id, user, ProjectAccess.EDIT)
    if not await storage_service.blob_exists(
        bucket_name=body.gcs_bucket, object_name=body.gcs_object_name
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Upload not found — finalise after the PUT completes",
        )
    await shoot_service.attach_call_sheet(
        session, shoot=shoot, actor=user, gcs_object_name=body.gcs_object_name
    )
    await session.commit()
    await session.refresh(shoot)
    return ShootPublic.model_validate(shoot)


__all__ = ["projects_router", "shoots_router"]
