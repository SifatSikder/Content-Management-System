"""Cast-member endpoints + release-form upload."""

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
from app.models.cast_member import CastMemberModel
from app.models.project import ProjectModel
from app.schemas.cast_member import (
    ALLOWED_RELEASE_CONTENT_TYPES,
    CastMemberPublic,
    CreateCastMemberBody,
    FinaliseReleaseBody,
    InitReleaseUploadBody,
    InitReleaseUploadResponse,
    UpdateCastMemberBody,
)
from app.services import cast_service, storage_service
from app.services.cast_service import CastMemberNotFoundError

log = structlog.get_logger(__name__)

projects_router = APIRouter(prefix="/projects/{project_id}/cast", tags=["casting"])
cast_router = APIRouter(prefix="/cast", tags=["casting"])


_RELEASE_EXTENSIONS = {
    "application/pdf": "pdf",
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


def _release_object_name(project_id: uuid.UUID, cast_id: uuid.UUID, content_type: str) -> str:
    ext = _RELEASE_EXTENSIONS.get(content_type, "bin")
    return f"projects/{project_id}/cast/{cast_id}/release_{uuid.uuid4()}.{ext}"


# ---------- collection ----------

@projects_router.post(
    "",
    response_model=CastMemberPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Add a cast member to a project",
)
async def post_cast(
    body: CreateCastMemberBody,
    project: Annotated[ProjectModel, Depends(require_project_access(ProjectAccess.EDIT))],
    user: CurrentUser,
    session: SessionDep,
) -> CastMemberPublic:
    cast = await cast_service.create_cast_member(
        session,
        project=project,
        actor=user,
        name=body.name,
        role_description=body.role_description,
        contact_email=str(body.contact_email) if body.contact_email else None,
        contact_phone=body.contact_phone,
    )
    await session.commit()
    await session.refresh(cast)
    return CastMemberPublic.model_validate(cast)


@projects_router.get(
    "",
    response_model=list[CastMemberPublic],
    summary="List cast members for a project",
)
async def get_cast(
    project: Annotated[ProjectModel, Depends(require_project_access(ProjectAccess.VIEW))],
    session: SessionDep,
) -> list[CastMemberPublic]:
    cast = await cast_service.list_cast_members(session, project_id=project.id)
    return [CastMemberPublic.model_validate(c) for c in cast]


# ---------- instance ----------

async def _project_for_cast(session: SessionDep, cast: CastMemberModel) -> ProjectModel:
    project_q = await session.execute(
        select(ProjectModel).where(
            ProjectModel.id == cast.project_id,
            ProjectModel.deleted_at.is_(None),
        )
    )
    project = project_q.scalar_one_or_none()
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project


async def _load_cast_and_project(
    session: SessionDep, cast_id: uuid.UUID, user: CurrentUser, level: ProjectAccess
) -> tuple[CastMemberModel, ProjectModel]:
    try:
        cast = await cast_service.get_cast_member(session, cast_id=cast_id)
    except CastMemberNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cast member not found") from exc
    project = await _project_for_cast(session, cast)
    if not await _user_can_access_project(session, user, project, level):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient project access")
    return cast, project


@cast_router.get(
    "/{cast_id}", response_model=CastMemberPublic, summary="Get one cast member"
)
async def get_one_cast(
    cast_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> CastMemberPublic:
    cast, _ = await _load_cast_and_project(session, cast_id, user, ProjectAccess.VIEW)
    return CastMemberPublic.model_validate(cast)


@cast_router.patch(
    "/{cast_id}", response_model=CastMemberPublic, summary="Update a cast member"
)
async def patch_cast(
    cast_id: uuid.UUID,
    body: UpdateCastMemberBody,
    user: CurrentUser,
    session: SessionDep,
) -> CastMemberPublic:
    cast, _ = await _load_cast_and_project(session, cast_id, user, ProjectAccess.EDIT)
    updates = body.model_dump(exclude_unset=True)
    if "contact_email" in updates and updates["contact_email"] is not None:
        updates["contact_email"] = str(updates["contact_email"])
    await cast_service.update_cast_member(session, cast=cast, actor=user, fields=updates)
    await session.commit()
    await session.refresh(cast)
    return CastMemberPublic.model_validate(cast)


@cast_router.post(
    "/{cast_id}/confirm",
    response_model=CastMemberPublic,
    summary="Confirm a cast member (may auto-advance the project)",
)
async def post_confirm_cast(
    cast_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> CastMemberPublic:
    cast, project = await _load_cast_and_project(session, cast_id, user, ProjectAccess.EDIT)
    await cast_service.confirm_cast_member(
        session, cast=cast, project=project, actor=user, confirmed=True
    )
    await session.commit()
    await session.refresh(cast)
    return CastMemberPublic.model_validate(cast)


@cast_router.post(
    "/{cast_id}/unconfirm",
    response_model=CastMemberPublic,
    summary="Un-confirm a cast member",
)
async def post_unconfirm_cast(
    cast_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> CastMemberPublic:
    cast, project = await _load_cast_and_project(session, cast_id, user, ProjectAccess.EDIT)
    await cast_service.confirm_cast_member(
        session, cast=cast, project=project, actor=user, confirmed=False
    )
    await session.commit()
    await session.refresh(cast)
    return CastMemberPublic.model_validate(cast)


@cast_router.delete(
    "/{cast_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a cast member",
)
async def delete_cast(
    cast_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> None:
    cast, _ = await _load_cast_and_project(session, cast_id, user, ProjectAccess.EDIT)
    await cast_service.delete_cast_member(session, cast=cast, actor=user)
    await session.commit()


# ---------- release-form upload ----------

@cast_router.post(
    "/{cast_id}/release/init-upload",
    response_model=InitReleaseUploadResponse,
    summary="Mint a GCS resumable session for a release form",
)
async def post_init_release_upload(
    cast_id: uuid.UUID,
    body: InitReleaseUploadBody,
    user: CurrentUser,
    session: SessionDep,
) -> InitReleaseUploadResponse:
    if body.content_type not in ALLOWED_RELEASE_CONTENT_TYPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Content type {body.content_type!r} not allowed",
        )
    cast, project = await _load_cast_and_project(session, cast_id, user, ProjectAccess.EDIT)
    settings = get_settings()
    bucket = settings.gcs_bucket_assets
    object_name = _release_object_name(project.id, cast.id, body.content_type)
    session_url = await storage_service.create_resumable_upload_session(
        bucket_name=bucket,
        object_name=object_name,
        content_type=body.content_type,
        size_bytes=body.size_bytes,
    )
    return InitReleaseUploadResponse(
        upload_session_url=session_url, gcs_bucket=bucket, gcs_object_name=object_name
    )


_RELEASE_URL_TTL_SECONDS = 15 * 60

# Map object-name extensions back to a serveable content type. Mirrors
# `_RELEASE_EXTENSIONS` above. Used by the release-url endpoint so the
# frontend can pick PDF vs image rendering without storing the type
# separately on the cast row.
_EXTENSION_TO_CONTENT_TYPE = {
    "pdf": "application/pdf",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
}


@cast_router.get(
    "/{cast_id}/release/url",
    summary="Get a short-lived signed read URL for a cast member's release form",
)
async def get_release_url(
    cast_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> dict[str, int | str]:
    cast, _ = await _load_cast_and_project(session, cast_id, user, ProjectAccess.VIEW)
    if cast.release_form_object_name is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No release form on file")
    settings = get_settings()
    ext = cast.release_form_object_name.rsplit(".", 1)[-1].lower()
    content_type = _EXTENSION_TO_CONTENT_TYPE.get(ext, "application/octet-stream")
    url = await storage_service.signed_read_url(
        bucket_name=settings.gcs_bucket_assets,
        object_name=cast.release_form_object_name,
        expires_in_seconds=_RELEASE_URL_TTL_SECONDS,
        # Force inline rendering so Chrome shows the PDF in an iframe rather
        # than downloading — resumable uploads land with unreliable Content-Type.
        response_content_type=content_type,
        response_content_disposition="inline",
    )
    return {
        "url": url,
        "content_type": content_type,
        "expires_in_seconds": _RELEASE_URL_TTL_SECONDS,
    }


@cast_router.post(
    "/{cast_id}/release",
    response_model=CastMemberPublic,
    summary="Finalise a release-form upload (stores GCS object name on the cast row)",
)
async def post_finalise_release(
    cast_id: uuid.UUID,
    body: FinaliseReleaseBody,
    user: CurrentUser,
    session: SessionDep,
) -> CastMemberPublic:
    cast, _ = await _load_cast_and_project(session, cast_id, user, ProjectAccess.EDIT)
    if not await storage_service.blob_exists(
        bucket_name=body.gcs_bucket, object_name=body.gcs_object_name
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Upload not found — finalise after the PUT completes",
        )
    await cast_service.attach_release_form(
        session, cast=cast, actor=user, gcs_object_name=body.gcs_object_name
    )
    await session.commit()
    await session.refresh(cast)
    return CastMemberPublic.model_validate(cast)


__all__ = ["cast_router", "projects_router"]
