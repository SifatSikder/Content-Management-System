"""Raw-cut submission endpoints — director uploads source material at the
end of `shoot_done`. First submission advances the project to `editing`."""

from __future__ import annotations

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.auth.dependencies import (
    CurrentUser,
    ProjectAccess,
    SessionDep,
    require_action,
    require_project_access,
)
from app.config import get_settings
from app.models.project import ProjectModel
from app.schemas.raw_cut import (
    ALLOWED_RAW_CUT_CONTENT_TYPES,
    FinaliseRawCutBody,
    InitRawCutUploadBody,
    InitRawCutUploadResponse,
    RawCutPublic,
)
from app.services import raw_cut_service, storage_service

log = structlog.get_logger(__name__)

projects_router = APIRouter(
    prefix="/projects/{project_id}/raw-cuts", tags=["raw-cuts"]
)


_EXTENSIONS = {
    "video/mp4": "mp4",
    "video/quicktime": "mov",
    "video/x-msvideo": "avi",
}


def _new_object_name(project_id: uuid.UUID, content_type: str) -> str:
    ext = _EXTENSIONS.get(content_type, "bin")
    return f"projects/{project_id}/raw-cuts/{uuid.uuid4()}.{ext}"


@projects_router.post(
    "/init-upload",
    response_model=InitRawCutUploadResponse,
    summary="Mint a GCS resumable upload session for a raw cut",
    dependencies=[Depends(require_action("raw_cut.submit"))],
)
async def post_init_upload(
    body: InitRawCutUploadBody,
    project: Annotated[
        ProjectModel, Depends(require_project_access(ProjectAccess.EDIT))
    ],
    request: Request,
) -> InitRawCutUploadResponse:
    if body.content_type not in ALLOWED_RAW_CUT_CONTENT_TYPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Content type {body.content_type!r} not allowed",
        )
    settings = get_settings()
    bucket = settings.gcs_bucket_video
    object_name = _new_object_name(project.id, body.content_type)
    origin = request.headers.get("origin")
    session_url = await storage_service.create_resumable_upload_session(
        bucket_name=bucket,
        object_name=object_name,
        content_type=body.content_type,
        size_bytes=body.size_bytes,
        origin=origin,
    )
    log.info(
        "raw_cut_upload_init",
        project_id=str(project.id),
        bucket=bucket,
        object_name=object_name,
        size_bytes=body.size_bytes,
    )
    return InitRawCutUploadResponse(
        upload_session_url=session_url,
        gcs_bucket=bucket,
        gcs_object_name=object_name,
    )


@projects_router.post(
    "",
    response_model=RawCutPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Finalise a raw-cut upload (advances stage to editing on first submission)",
    dependencies=[Depends(require_action("raw_cut.submit"))],
)
async def post_finalise(
    body: FinaliseRawCutBody,
    project: Annotated[
        ProjectModel, Depends(require_project_access(ProjectAccess.EDIT))
    ],
    user: CurrentUser,
    session: SessionDep,
) -> RawCutPublic:
    if not await storage_service.blob_exists(
        bucket_name=body.gcs_bucket, object_name=body.gcs_object_name
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Upload not found in storage — finalise after the PUT completes",
        )
    row = await raw_cut_service.submit_raw_cut(
        session,
        project=project,
        uploader=user,
        gcs_bucket=body.gcs_bucket,
        gcs_object_name=body.gcs_object_name,
        content_type=body.content_type,
        byte_size=body.size_bytes,
        original_filename=body.original_filename,
    )
    await session.commit()
    await session.refresh(row, attribute_names=["uploader"])
    return RawCutPublic.model_validate(row)


@projects_router.get(
    "",
    response_model=list[RawCutPublic],
    summary="List raw-cut submissions for a project",
)
async def get_raw_cuts(
    project: Annotated[
        ProjectModel, Depends(require_project_access(ProjectAccess.VIEW))
    ],
    session: SessionDep,
) -> list[RawCutPublic]:
    rows = await raw_cut_service.list_raw_cuts(session, project_id=project.id)
    return [RawCutPublic.model_validate(r) for r in rows]


__all__ = ["projects_router"]
