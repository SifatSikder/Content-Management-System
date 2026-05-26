"""Location endpoints + photo upload.

Two routers:
  * `projects_router`  — collection-scoped: list/create under a project.
  * `locations_router` — instance-scoped: read/update/delete/confirm,
    photo init-upload / finalise / delete.

Permissions: same model as Phase 1 — VIEW for read endpoints, EDIT for
mutations, MANAGE for confirm + delete. Stage auto-advance lives in the
service; the routes are thin.
"""

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
    require_action,
    require_project_access,
)
from app.config import get_settings
from app.models.location import LocationModel
from app.models.project import ProjectModel
from app.schemas.location import (
    ALLOWED_PHOTO_CONTENT_TYPES,
    CreateLocationBody,
    FinalisePhotoBody,
    InitPhotoUploadBody,
    InitPhotoUploadResponse,
    LocationPhotoPublic,
    LocationPublic,
    UpdateLocationBody,
)
from app.services import location_service, storage_service
from app.services.location_service import (
    LocationLockError,
    LocationNotFoundError,
    LocationPhotoNotFoundError,
)

log = structlog.get_logger(__name__)

projects_router = APIRouter(prefix="/projects/{project_id}/locations", tags=["locations"])
locations_router = APIRouter(prefix="/locations", tags=["locations"])


_PHOTO_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/heic": "heic",
}


def _photo_object_name(project_id: uuid.UUID, location_id: uuid.UUID, content_type: str) -> str:
    ext = _PHOTO_EXTENSIONS.get(content_type, "bin")
    return f"projects/{project_id}/locations/{location_id}/{uuid.uuid4()}.{ext}"


# ---------- collection (project-scoped) ----------

@projects_router.post(
    "",
    response_model=LocationPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Create a location for a project",
)
async def post_location(
    body: CreateLocationBody,
    project: Annotated[ProjectModel, Depends(require_project_access(ProjectAccess.EDIT))],
    user: CurrentUser,
    session: SessionDep,
) -> LocationPublic:
    location = await location_service.create_location(
        session,
        project=project,
        actor=user,
        address=body.address,
        latitude=body.latitude,
        longitude=body.longitude,
        contact_name=body.contact_name,
        contact_phone=body.contact_phone,
        scheduled_at=body.scheduled_at,
    )
    await session.commit()
    await session.refresh(location)
    return LocationPublic.model_validate(location)


@projects_router.get(
    "",
    response_model=list[LocationPublic],
    summary="List locations for a project",
)
async def get_locations(
    project: Annotated[ProjectModel, Depends(require_project_access(ProjectAccess.VIEW))],
    session: SessionDep,
) -> list[LocationPublic]:
    locations = await location_service.list_locations(session, project_id=project.id)
    return [LocationPublic.model_validate(loc) for loc in locations]


# ---------- explicit lock action ----------

@projects_router.post(
    "/lock",
    summary="Lock the location and advance the project (location.lock action)",
    dependencies=[Depends(require_action("location.lock"))],
)
async def post_lock_location(
    project: Annotated[
        ProjectModel, Depends(require_project_access(ProjectAccess.VIEW))
    ],
    user: CurrentUser,
    session: SessionDep,
) -> dict[str, str]:
    try:
        await location_service.lock_location(session, project=project, actor=user)
    except LocationLockError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await session.commit()
    return {"status": "locked"}


# ---------- instance ----------

async def _project_for_location(session: SessionDep, location: LocationModel) -> ProjectModel:
    project_q = await session.execute(
        select(ProjectModel).where(
            ProjectModel.id == location.project_id,
            ProjectModel.deleted_at.is_(None),
        )
    )
    project = project_q.scalar_one_or_none()
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project


async def _load_location_and_project(
    session: SessionDep, location_id: uuid.UUID, user: CurrentUser, level: ProjectAccess
) -> tuple[LocationModel, ProjectModel]:
    try:
        location = await location_service.get_location(session, location_id=location_id)
    except LocationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Location not found") from exc
    project = await _project_for_location(session, location)
    if not await _user_can_access_project(session, user, project, level):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient project access")
    return location, project


@locations_router.get(
    "/{location_id}", response_model=LocationPublic, summary="Get one location"
)
async def get_location(
    location_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> LocationPublic:
    location, _ = await _load_location_and_project(session, location_id, user, ProjectAccess.VIEW)
    return LocationPublic.model_validate(location)


@locations_router.patch(
    "/{location_id}", response_model=LocationPublic, summary="Update a location"
)
async def patch_location(
    location_id: uuid.UUID,
    body: UpdateLocationBody,
    user: CurrentUser,
    session: SessionDep,
) -> LocationPublic:
    location, _ = await _load_location_and_project(session, location_id, user, ProjectAccess.EDIT)
    await location_service.update_location(
        session, location=location, actor=user, fields=body.model_dump(exclude_unset=True)
    )
    await session.commit()
    await session.refresh(location)
    return LocationPublic.model_validate(location)


@locations_router.post(
    "/{location_id}/confirm",
    response_model=LocationPublic,
    summary="Mark a location confirmed (advances stage)",
)
async def post_confirm_location(
    location_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> LocationPublic:
    location, project = await _load_location_and_project(
        session, location_id, user, ProjectAccess.EDIT
    )
    await location_service.confirm_location(
        session, location=location, project=project, actor=user, confirmed=True
    )
    await session.commit()
    await session.refresh(location)
    return LocationPublic.model_validate(location)


@locations_router.post(
    "/{location_id}/unconfirm",
    response_model=LocationPublic,
    summary="Un-mark a confirmed location",
)
async def post_unconfirm_location(
    location_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> LocationPublic:
    location, project = await _load_location_and_project(
        session, location_id, user, ProjectAccess.EDIT
    )
    await location_service.confirm_location(
        session, location=location, project=project, actor=user, confirmed=False
    )
    await session.commit()
    await session.refresh(location)
    return LocationPublic.model_validate(location)


@locations_router.delete(
    "/{location_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a location",
)
async def delete_location(
    location_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> None:
    location, _ = await _load_location_and_project(
        session, location_id, user, ProjectAccess.EDIT
    )
    await location_service.delete_location(session, location=location, actor=user)
    await session.commit()


# ---------- photo upload ----------

@locations_router.post(
    "/{location_id}/photos/init-upload",
    response_model=InitPhotoUploadResponse,
    summary="Mint a GCS resumable upload session for a location photo",
)
async def post_init_photo_upload(
    location_id: uuid.UUID,
    body: InitPhotoUploadBody,
    user: CurrentUser,
    session: SessionDep,
) -> InitPhotoUploadResponse:
    if body.content_type not in ALLOWED_PHOTO_CONTENT_TYPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Content type {body.content_type!r} not allowed",
        )
    location, project = await _load_location_and_project(
        session, location_id, user, ProjectAccess.EDIT
    )
    settings = get_settings()
    bucket = settings.gcs_bucket_assets
    object_name = _photo_object_name(project.id, location.id, body.content_type)
    session_url = await storage_service.create_resumable_upload_session(
        bucket_name=bucket,
        object_name=object_name,
        content_type=body.content_type,
        size_bytes=body.size_bytes,
    )
    return InitPhotoUploadResponse(
        upload_session_url=session_url, gcs_bucket=bucket, gcs_object_name=object_name
    )


@locations_router.post(
    "/{location_id}/photos",
    response_model=LocationPhotoPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Finalise a photo upload",
)
async def post_finalise_photo(
    location_id: uuid.UUID,
    body: FinalisePhotoBody,
    user: CurrentUser,
    session: SessionDep,
) -> LocationPhotoPublic:
    if body.content_type not in ALLOWED_PHOTO_CONTENT_TYPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Content type {body.content_type!r} not allowed",
        )
    location, _ = await _load_location_and_project(session, location_id, user, ProjectAccess.EDIT)
    if not await storage_service.blob_exists(
        bucket_name=body.gcs_bucket, object_name=body.gcs_object_name
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Upload not found — finalise after the PUT completes",
        )
    photo = await location_service.attach_photo(
        session,
        location=location,
        uploader=user,
        gcs_bucket=body.gcs_bucket,
        gcs_object_name=body.gcs_object_name,
        content_type=body.content_type,
        size_bytes=body.size_bytes,
    )
    await session.commit()
    await session.refresh(photo)
    return LocationPhotoPublic.model_validate(photo)


_PHOTO_URL_TTL_SECONDS = 15 * 60


@locations_router.get(
    "/photos/{photo_id}/url",
    summary="Get a short-lived signed read URL for a location photo",
)
async def get_photo_url(
    photo_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> dict[str, int | str]:
    try:
        photo = await location_service.get_photo(session, photo_id=photo_id)
    except LocationPhotoNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Photo not found") from exc
    location = await location_service.get_location(session, location_id=photo.location_id)
    project = await _project_for_location(session, location)
    if not await _user_can_access_project(session, user, project, ProjectAccess.VIEW):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient project access")
    url = await storage_service.signed_read_url(
        bucket_name=photo.gcs_bucket,
        object_name=photo.gcs_object_name,
        expires_in_seconds=_PHOTO_URL_TTL_SECONDS,
        response_content_type=photo.content_type,
        response_content_disposition="inline",
    )
    return {"url": url, "expires_in_seconds": _PHOTO_URL_TTL_SECONDS}


@locations_router.delete(
    "/photos/{photo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a location photo",
)
async def delete_photo(
    photo_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> None:
    try:
        photo = await location_service.get_photo(session, photo_id=photo_id)
    except LocationPhotoNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Photo not found") from exc
    # Resolve project for permission check.
    location = await location_service.get_location(session, location_id=photo.location_id)
    project = await _project_for_location(session, location)
    if not await _user_can_access_project(session, user, project, ProjectAccess.EDIT):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient project access")
    await location_service.delete_photo(session, photo=photo, actor=user)
    await session.commit()


__all__ = ["locations_router", "projects_router"]
