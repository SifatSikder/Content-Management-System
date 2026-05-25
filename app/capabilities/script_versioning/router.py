"""Script endpoints — versions, comments, and the script-phase stage transitions."""

from __future__ import annotations

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    CurrentUser,
    ProjectAccess,
    SessionDep,
    _user_can_access_project,
    require_action,
    require_project_access,
)
from app.models.project import ProjectModel
from app.models.script import ScriptModel, ScriptVersionModel
from app.schemas.script import (
    CommentPublic,
    CreateCommentBody,
    CreateVersionBody,
    VersionPublic,
)
from app.services import script_service
from app.services.script_service import (
    IllegalStageTransitionError,
    ScriptCommentNotFoundError,
    ScriptVersionNotFoundError,
)

log = structlog.get_logger(__name__)

# Versions are nested under /projects/{project_id}/scripts.
projects_router = APIRouter(prefix="/projects/{project_id}/scripts", tags=["scripts"])
# Comments operate on a version id directly (so no project_id in the path).
scripts_router = APIRouter(prefix="/scripts", tags=["scripts"])




# ---------- versions ----------

@projects_router.post(
    "/versions",
    response_model=VersionPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new script version (markdown)",
)
async def post_version(
    body: CreateVersionBody,
    project: Annotated[ProjectModel, Depends(require_project_access(ProjectAccess.EDIT))],
    user: CurrentUser,
    session: SessionDep,
) -> VersionPublic:
    try:
        version = await script_service.add_version(
            session, project=project, author=user, body_markdown=body.body_markdown
        )
    except IllegalStageTransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await session.commit()
    await session.refresh(version)
    return VersionPublic.model_validate(version)


@projects_router.get(
    "/versions", response_model=list[VersionPublic], summary="List script versions"
)
async def get_versions(
    project: Annotated[ProjectModel, Depends(require_project_access(ProjectAccess.VIEW))],
    session: SessionDep,
) -> list[VersionPublic]:
    versions = await script_service.list_versions(session, project=project)
    return [VersionPublic.model_validate(v) for v in versions]


@projects_router.get(
    "/versions/{version_id}",
    response_model=VersionPublic,
    summary="Get one script version",
)
async def get_version(
    project: Annotated[ProjectModel, Depends(require_project_access(ProjectAccess.VIEW))],
    version_id: uuid.UUID,
    session: SessionDep,
) -> VersionPublic:
    try:
        version = await script_service.get_version(session, version_id=version_id)
    except ScriptVersionNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version not found") from exc

    # The version must belong to this project's script.
    script_q = await session.execute(
        select(ScriptModel).where(ScriptModel.id == version.script_id)
    )
    script = script_q.scalar_one()
    if script.project_id != project.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version not found")

    return VersionPublic.model_validate(version)


# ---------- script-phase stage transitions ----------

@projects_router.post(
    "/submit",
    summary="Submit the current script for review",
)
async def post_submit(
    project: Annotated[ProjectModel, Depends(require_project_access(ProjectAccess.EDIT))],
    user: CurrentUser,
    session: SessionDep,
) -> dict[str, str]:
    try:
        await script_service.submit_script(session, project=project, actor=user)
    except IllegalStageTransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await session.commit()
    return {"status": "submitted"}


@projects_router.post(
    "/lock",
    summary="Lock the script (`script_versioning.lock` action)",
    dependencies=[Depends(require_action("script_versioning.lock"))],
)
async def post_lock(
    project: Annotated[ProjectModel, Depends(require_project_access(ProjectAccess.VIEW))],
    user: CurrentUser,
    session: SessionDep,
) -> dict[str, str]:
    try:
        await script_service.lock_script(session, project=project, actor=user)
    except IllegalStageTransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await session.commit()
    return {"status": "locked"}


@projects_router.post(
    "/unlock",
    summary="Unlock the script (`script_versioning.unlock` action)",
    dependencies=[Depends(require_action("script_versioning.unlock"))],
)
async def post_unlock(
    project: Annotated[ProjectModel, Depends(require_project_access(ProjectAccess.VIEW))],
    user: CurrentUser,
    session: SessionDep,
) -> dict[str, str]:
    try:
        await script_service.unlock_script(session, project=project, actor=user)
    except IllegalStageTransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await session.commit()
    return {"status": "unlocked"}


# ---------- comments (operate on version_id directly) ----------

async def _project_for_version(
    session: AsyncSession, version_id: uuid.UUID
) -> ProjectModel:
    """Internal helper: load the project that owns a script version."""
    version_q = await session.execute(
        select(ScriptVersionModel).where(ScriptVersionModel.id == version_id)
    )
    version = version_q.scalar_one_or_none()
    if version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version not found")
    script_q = await session.execute(
        select(ScriptModel).where(ScriptModel.id == version.script_id)
    )
    script = script_q.scalar_one()
    project_q = await session.execute(
        select(ProjectModel).where(
            ProjectModel.id == script.project_id, ProjectModel.deleted_at.is_(None)
        )
    )
    project = project_q.scalar_one_or_none()
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project


@scripts_router.post(
    "/versions/{version_id}/comments",
    response_model=CommentPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Add a comment to a script version",
)
async def post_comment(
    version_id: uuid.UUID,
    body: CreateCommentBody,
    user: CurrentUser,
    session: SessionDep,
) -> CommentPublic:
    project = await _project_for_version(session, version_id)
    if not await _user_can_access_project(session, user, project, ProjectAccess.VIEW):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient project access")

    try:
        version = await script_service.get_version(session, version_id=version_id)
    except ScriptVersionNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version not found") from exc

    comment = await script_service.add_comment(
        session,
        version=version,
        author=user,
        body=body.body,
        paragraph_anchor=body.paragraph_anchor,
    )
    await session.commit()
    await session.refresh(comment)
    return CommentPublic.model_validate(comment)


@scripts_router.get(
    "/versions/{version_id}/comments",
    response_model=list[CommentPublic],
    summary="List comments on a script version",
)
async def get_comments(
    version_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> list[CommentPublic]:
    project = await _project_for_version(session, version_id)
    if not await _user_can_access_project(session, user, project, ProjectAccess.VIEW):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient project access")
    comments = await script_service.list_comments(session, version_id=version_id)
    return [CommentPublic.model_validate(c) for c in comments]


@scripts_router.post(
    "/comments/{comment_id}/resolve",
    response_model=CommentPublic,
    summary="Mark a comment resolved",
)
async def post_resolve(
    comment_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> CommentPublic:
    try:
        comment = await script_service.get_comment(session, comment_id=comment_id)
    except ScriptCommentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Comment not found") from exc
    project = await _project_for_version(session, comment.version_id)
    if not await _user_can_access_project(session, user, project, ProjectAccess.EDIT):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient project access")
    await script_service.resolve_comment(session, comment=comment, actor=user)
    await session.commit()
    await session.refresh(comment)
    return CommentPublic.model_validate(comment)


@scripts_router.post(
    "/comments/{comment_id}/reopen",
    response_model=CommentPublic,
    summary="Re-open a previously resolved comment",
)
async def post_reopen(
    comment_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> CommentPublic:
    try:
        comment = await script_service.get_comment(session, comment_id=comment_id)
    except ScriptCommentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Comment not found") from exc
    project = await _project_for_version(session, comment.version_id)
    if not await _user_can_access_project(session, user, project, ProjectAccess.EDIT):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient project access")
    await script_service.reopen_comment(session, comment=comment, actor=user)
    await session.commit()
    await session.refresh(comment)
    return CommentPublic.model_validate(comment)


__all__ = ["projects_router", "scripts_router"]
