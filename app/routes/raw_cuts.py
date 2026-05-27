"""Raw-cut submission endpoints — director uploads source material at the
end of `shooting`. First submission advances the project to `editing`."""

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
from sqlalchemy import select

from app.config import get_settings
from app.models.project import ProjectModel
from app.models.shoot import ShootModel
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


def _new_object_name(
    project_id: uuid.UUID, shoot_id: uuid.UUID, content_type: str
) -> str:
    ext = _EXTENSIONS.get(content_type, "bin")
    return (
        f"projects/{project_id}/shoots/{shoot_id}/raw-cuts/{uuid.uuid4()}.{ext}"
    )


async def _ensure_shoot_in_project(
    session: SessionDep, *, project_id: uuid.UUID, shoot_id: uuid.UUID
) -> None:
    row = await session.execute(
        select(ShootModel.id).where(
            ShootModel.id == shoot_id, ShootModel.project_id == project_id
        )
    )
    if row.first() is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Shoot not found on this project"
        )


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
    session: SessionDep,
) -> InitRawCutUploadResponse:
    if body.content_type not in ALLOWED_RAW_CUT_CONTENT_TYPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Content type {body.content_type!r} not allowed",
        )
    await _ensure_shoot_in_project(
        session, project_id=project.id, shoot_id=body.shoot_id
    )
    settings = get_settings()
    bucket = settings.gcs_bucket_video
    object_name = _new_object_name(project.id, body.shoot_id, body.content_type)
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
    await _ensure_shoot_in_project(
        session, project_id=project.id, shoot_id=body.shoot_id
    )
    row = await raw_cut_service.submit_raw_cut(
        session,
        project=project,
        shoot_id=body.shoot_id,
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


_RAW_CUT_URL_TTL_SECONDS = 60 * 60  # 1 hour — big files take longer to grab


@projects_router.get(
    "/{raw_cut_id}/url",
    summary="Get a short-lived signed URL for a raw cut",
)
async def get_raw_cut_url(
    raw_cut_id: uuid.UUID,
    project: Annotated[
        ProjectModel, Depends(require_project_access(ProjectAccess.VIEW))
    ],
    session: SessionDep,
    disposition: str = "attachment",
) -> dict[str, int | str]:
    """Mint a signed URL for the raw cut. `disposition=attachment`
    (default) triggers a browser download — editors pull the bytes
    into their NLE. `disposition=inline` lets the editor preview the
    file via a `<video>` element before deciding to download."""
    if disposition not in ("attachment", "inline"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "disposition must be 'attachment' or 'inline'",
        )
    try:
        row = await raw_cut_service.get_raw_cut(session, raw_cut_id=raw_cut_id)
    except raw_cut_service.RawCutSubmissionNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Raw cut not found") from exc
    if row.project_id != project.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Raw cut not found")
    if disposition == "attachment" and row.original_filename:
        cd = f'attachment; filename="{row.original_filename}"'
    else:
        cd = disposition
    url = await storage_service.signed_read_url(
        bucket_name=row.gcs_bucket,
        object_name=row.gcs_object_name,
        expires_in_seconds=_RAW_CUT_URL_TTL_SECONDS,
        response_content_type=row.content_type,
        response_content_disposition=cd,
    )
    return {
        "url": url,
        "expires_in_seconds": _RAW_CUT_URL_TTL_SECONDS,
    }


__all__ = ["projects_router"]
