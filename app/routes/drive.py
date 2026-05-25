"""Google Drive endpoints (Phase 3 Task 3.3).

Two router instances, mirroring the scripts/edits split:
- `auth_router`   — `/auth/google/drive/*` (per-user OAuth)
- `projects_router` — `/projects/{id}/drive/*` (folder attach + detach)

Import-gdoc lives in `app.routes.scripts` because it produces a ScriptVersion.
"""

from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from app.auth.dependencies import (
    CurrentUser,
    ProjectAccess,
    SessionDep,
    require_project_access,
)
from app.config import get_settings
from app.core.crypto import TokenDecryptionError, TokenEncryptionNotConfiguredError
from app.models.project import ProjectModel
from app.schemas.drive import (
    AttachDriveBody,
    DriveConnectionPublic,
    DriveDocumentListResponse,
    DriveDocumentPublic,
    StartConnectResponse,
)
from app.schemas.project import ProjectPublic
from app.services import drive_service
from app.services.drive_service import (
    DriveNotConfiguredError,
    GoogleApiError,
    InvalidOAuthStateError,
    NotConnectedError,
)

log = structlog.get_logger(__name__)

auth_router = APIRouter(prefix="/auth/google/drive", tags=["drive"])
projects_router = APIRouter(prefix="/projects/{project_id}/drive", tags=["drive"])
files_router = APIRouter(prefix="/drive", tags=["drive"])


@files_router.get(
    "/documents",
    response_model=DriveDocumentListResponse,
    summary="List the calling user's Google Docs from Drive (newest-modified first)",
)
async def get_documents(
    user: CurrentUser,
    session: SessionDep,
    q: Annotated[str | None, Query(description="Title substring filter")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> DriveDocumentListResponse:
    """Surface the user's Google Docs for the import picker.

    Returns 412 if the user hasn't connected Drive yet — the frontend
    catches that and routes them through the OAuth consent flow instead
    of throwing.
    """
    try:
        access_token = await drive_service.access_token_for_user(
            session, user_id=user.id
        )
    except NotConnectedError as exc:
        raise HTTPException(
            status.HTTP_412_PRECONDITION_FAILED,
            "Drive is not connected",
        ) from exc
    except (DriveNotConfiguredError, TokenEncryptionNotConfiguredError) as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Drive is not configured on this server",
        ) from exc
    except TokenDecryptionError as exc:
        await drive_service.delete_connection(session, user_id=user.id)
        await session.commit()
        raise HTTPException(
            status.HTTP_412_PRECONDITION_FAILED,
            "Drive credentials are stale; reconnect",
        ) from exc

    try:
        files = await drive_service.list_documents(
            access_token=access_token, query=q, page_size=limit
        )
    except GoogleApiError as exc:
        if exc.status_code in (401, 403):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "Drive denied the request"
            ) from exc
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "Drive returned an error"
        ) from exc

    return DriveDocumentListResponse(
        items=[
            DriveDocumentPublic(
                id=f["id"],
                name=f.get("name", ""),
                modified_time=f.get("modifiedTime"),
                web_view_link=f.get("webViewLink"),
            )
            for f in files
        ]
    )


# ---------- per-user OAuth ----------


@auth_router.post(
    "/start",
    response_model=StartConnectResponse,
    summary="Start the Google Drive consent flow",
)
async def post_start(user: CurrentUser) -> StartConnectResponse:
    try:
        url = drive_service.build_oauth_url(user.id)
    except DriveNotConfiguredError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Google Drive OAuth is not configured on this server",
        ) from exc
    return StartConnectResponse(url=url)


@auth_router.get(
    "/callback",
    summary="OAuth redirect target — exchanges code, persists token, redirects to frontend",
    include_in_schema=False,
)
async def get_callback(
    session: SessionDep,
    code: Annotated[str | None, Query()] = None,
    state: Annotated[str | None, Query()] = None,
    error: Annotated[str | None, Query()] = None,
) -> RedirectResponse:
    settings = get_settings()
    base = settings.google_drive_post_auth_redirect

    if error:
        log.warning("drive_oauth_user_denied", error=error)
        return RedirectResponse(f"{base}?drive=error&reason={error}")

    if not code or not state:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Missing code or state")

    try:
        user_id = drive_service.verify_state(state)
    except InvalidOAuthStateError as exc:
        log.warning("drive_oauth_bad_state", error=str(exc))
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid OAuth state") from exc

    try:
        result = await drive_service.exchange_code(code)
    except (DriveNotConfiguredError, GoogleApiError) as exc:
        log.error("drive_oauth_exchange_failed", error=str(exc))
        return RedirectResponse(f"{base}?drive=error&reason=token_exchange")

    try:
        await drive_service.upsert_connection(
            session,
            user_id=user_id,
            google_email=result.google_email,
            refresh_token=result.refresh_token,
            scopes=result.scopes,
        )
    except TokenEncryptionNotConfiguredError as exc:
        log.error("drive_oauth_no_encryption_key", error=str(exc))
        return RedirectResponse(f"{base}?drive=error&reason=server_not_configured")
    await session.commit()

    return RedirectResponse(f"{base}?drive=connected")


@auth_router.get(
    "/me",
    response_model=DriveConnectionPublic,
    summary="Return the calling user's Drive connection (404 if none)",
)
async def get_me(user: CurrentUser, session: SessionDep) -> DriveConnectionPublic:
    row = await drive_service.get_connection(session, user_id=user.id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No Drive connection")
    return DriveConnectionPublic.model_validate(row)


@auth_router.delete(
    "/disconnect",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Forget the calling user's Drive refresh token",
)
async def delete_disconnect(user: CurrentUser, session: SessionDep) -> None:
    removed = await drive_service.delete_connection(session, user_id=user.id)
    if removed:
        await session.commit()
        log.info("drive_disconnected", user_id=str(user.id))


# ---------- project ↔ Drive folder attach ----------


@projects_router.post(
    "/attach",
    response_model=ProjectPublic,
    summary="Attach a Google Drive folder to the project",
)
async def post_attach(
    body: AttachDriveBody,
    project: Annotated[ProjectModel, Depends(require_project_access(ProjectAccess.EDIT))],
    session: SessionDep,
) -> ProjectPublic:
    project.drive_folder_id = body.folder_id
    project.drive_folder_url = body.folder_url
    await session.commit()
    await session.refresh(project)
    return ProjectPublic.model_validate(project)


@projects_router.delete(
    "/attach",
    response_model=ProjectPublic,
    summary="Detach the project's Drive folder",
)
async def delete_attach(
    project: Annotated[ProjectModel, Depends(require_project_access(ProjectAccess.EDIT))],
    session: SessionDep,
) -> ProjectPublic:
    project.drive_folder_id = None
    project.drive_folder_url = None
    await session.commit()
    await session.refresh(project)
    return ProjectPublic.model_validate(project)


__all__ = ["auth_router", "files_router", "projects_router"]
