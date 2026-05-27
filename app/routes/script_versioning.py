"""Script endpoints — versions, signoffs, comments, and lock action.

Mirrors the shape of `app/routes/idea_versioning.py`:
  GET    /projects/{id}/scripts                    — summary (lock state + latest version + signoffs)
  GET    /projects/{id}/scripts/versions           — list
  POST   /projects/{id}/scripts/versions           — create (owner-only)
  PATCH  /projects/{id}/scripts/versions/{id}      — edit in place (owner-only, pre-feedback)
  GET    /projects/{id}/scripts/versions/{id}/signoffs   — list signoffs for a version
  POST   /projects/{id}/scripts/versions/{id}/signoffs   — sign off (idea_versioning.signoff* style action key)
  GET    /projects/{id}/scripts/enhancement-candidates   — CEO + Director picker
  POST   /projects/{id}/scripts/request-enhancement      — owner pulls reviewers in
  POST   /projects/{id}/scripts/lock                     — advance to casting
  POST   /projects/{id}/scripts/unlock                   — owner-only revert
  + comment endpoints (unchanged)
"""

from __future__ import annotations

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
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
from app.models.user import UserModel
from app.schemas.script import (
    CommentPublic,
    CreateCommentBody,
    CreateSignoffBody,
    CreateVersionBody,
    ScriptSignoffPublic,
    ScriptSummaryPublic,
    UpdateVersionBody,
    VersionPublic,
)
from app.services import script_service
from app.services.script_service import (
    IllegalStageTransitionError,
    NoEnhancementReviewersError,
    ScriptCommentNotFoundError,
    ScriptLockGateError,
    ScriptNotFoundError,
    ScriptVersionNotEditableError,
    ScriptVersionNotFoundError,
    ScriptVersionNotSubmittedError,
)

log = structlog.get_logger(__name__)

# Versions are nested under /projects/{project_id}/scripts.
projects_router = APIRouter(prefix="/projects/{project_id}/scripts", tags=["scripts"])
# Comments operate on a version id directly (so no project_id in the path).
scripts_router = APIRouter(prefix="/scripts", tags=["scripts"])


# ---------- summary ----------


@projects_router.get(
    "",
    response_model=ScriptSummaryPublic,
    summary="Get the project's script-phase state (latest version + signoffs + lock gate)",
)
async def get_summary(
    project: Annotated[
        ProjectModel, Depends(require_project_access(ProjectAccess.VIEW))
    ],
    session: SessionDep,
) -> ScriptSummaryPublic:
    latest = await script_service.latest_version(session, project=project)
    signoffs: list[ScriptSignoffPublic] = []
    if latest is not None:
        rows = await script_service.list_signoffs(session, version_id=latest.id)
        signoffs = [ScriptSignoffPublic.model_validate(r) for r in rows]
    can_lock, pending = await script_service.lock_gate_status(
        session, project=project
    )
    reviewer_count = await script_service.reviewer_count(
        session, project=project
    )
    return ScriptSummaryPublic(
        locked_at=project.script_locked_at,
        locked_by=project.script_locked_by,
        latest_version=VersionPublic.model_validate(latest) if latest else None,
        latest_version_signoffs=signoffs,
        pending_reviewer_ids=pending,
        can_lock=can_lock,
        reviewer_count=reviewer_count,
    )


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
    # Owner-only — reviewers (CEO/Director) only sign off; they don't
    # draft new versions. Matches the patch + request-enhancement guards.
    if project.owner_id != user.id and not user.is_super_admin:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only the project owner can draft a new script version",
        )
    try:
        version = await script_service.add_version(
            session, project=project, author=user, body_markdown=body.body_markdown
        )
    except IllegalStageTransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await session.commit()
    return VersionPublic.model_validate(version)


@projects_router.patch(
    "/versions/{version_id}",
    response_model=VersionPublic,
    summary="Edit the current version body in place (owner-only, pre-feedback)",
)
async def patch_version(
    version_id: uuid.UUID,
    body: UpdateVersionBody,
    project: Annotated[
        ProjectModel, Depends(require_project_access(ProjectAccess.EDIT))
    ],
    user: CurrentUser,
    session: SessionDep,
) -> VersionPublic:
    if project.owner_id != user.id and not user.is_super_admin:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only the project owner can edit the draft"
        )
    try:
        version = await script_service.get_version(session, version_id=version_id)
    except ScriptVersionNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Script version not found") from exc
    try:
        await script_service.update_version_body(
            session,
            project=project,
            version=version,
            actor=user,
            body_markdown=body.body_markdown,
        )
    except ScriptVersionNotEditableError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await session.commit()
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


# ---------- signoffs ----------


@projects_router.get(
    "/versions/{version_id}/signoffs",
    response_model=list[ScriptSignoffPublic],
    summary="List signoffs for one specific script version",
)
async def get_signoffs(
    version_id: uuid.UUID,
    project: Annotated[
        ProjectModel, Depends(require_project_access(ProjectAccess.VIEW))
    ],
    session: SessionDep,
) -> list[ScriptSignoffPublic]:
    try:
        version = await script_service.get_version(session, version_id=version_id)
    except ScriptVersionNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Script version not found") from exc
    # Verify the version belongs to this project's script — RLS protects
    # cross-business but inside the same business we'd otherwise leak.
    script = await script_service.get_script(session, project=project)
    if script is None or version.script_id != script.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Script version not found")
    rows = await script_service.list_signoffs(session, version_id=version_id)
    reviewer_ids = {r.reviewer_id for r in rows}
    name_by_id: dict[uuid.UUID, tuple[str, str | None]] = {}
    if reviewer_ids:
        user_rows = await session.execute(
            select(UserModel.id, UserModel.name, UserModel.avatar_url).where(
                UserModel.id.in_(reviewer_ids)
            )
        )
        for uid, name, avatar in user_rows.all():
            name_by_id[uid] = (name, avatar)
    out: list[ScriptSignoffPublic] = []
    for r in rows:
        info = name_by_id.get(r.reviewer_id)
        out.append(
            ScriptSignoffPublic.model_validate(
                {
                    "id": r.id,
                    "script_version_id": r.script_version_id,
                    "reviewer_id": r.reviewer_id,
                    "reviewer_name": info[0] if info else None,
                    "reviewer_avatar_url": info[1] if info else None,
                    "decision": r.decision,
                    "comment": r.comment,
                    "created_at": r.created_at,
                }
            )
        )
    return out


@projects_router.post(
    "/versions/{version_id}/signoffs",
    response_model=ScriptSignoffPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Sign off on a script version (script_versioning.signoff action)",
    dependencies=[Depends(require_action("script_versioning.signoff"))],
)
async def post_signoff(
    version_id: uuid.UUID,
    body: CreateSignoffBody,
    project: Annotated[
        ProjectModel, Depends(require_project_access(ProjectAccess.VIEW))
    ],
    user: CurrentUser,
    session: SessionDep,
) -> ScriptSignoffPublic:
    try:
        version = await script_service.get_version(session, version_id=version_id)
    except ScriptVersionNotFoundError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Script version not found"
        ) from exc
    try:
        row = await script_service.add_signoff(
            session,
            project=project,
            version=version,
            reviewer=user,
            decision=body.decision,
            comment=body.comment,
        )
    except ScriptVersionNotSubmittedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await session.commit()
    # No explicit refresh — INSERT...RETURNING populates all server
    # defaults (id, timestamps) at flush time and `expire_on_commit=False`
    # keeps attributes accessible after commit. A refresh here would
    # issue a fresh SELECT which can hit "Could not refresh instance"
    # if the post-commit connection/RLS state has drifted.
    return ScriptSignoffPublic.model_validate(row)


# ---------- request enhancement ----------


@projects_router.get(
    "/enhancement-candidates",
    summary="List CEO + Director members the owner can ask for feedback",
)
async def get_enhancement_candidates(
    project: Annotated[
        ProjectModel, Depends(require_project_access(ProjectAccess.VIEW))
    ],
    session: SessionDep,
) -> dict[str, list[dict[str, str | None]]]:
    rows = await script_service.list_enhancement_candidates(
        session, project=project
    )
    latest = await script_service.latest_signoff_decision_by_user(
        session, project=project
    )
    return {
        "items": [
            {
                "user_id": str(uid),
                "email": email,
                "name": name,
                "role_key": role_key,
                "latest_decision": (
                    latest[uid].value if uid in latest else None
                ),
            }
            for uid, email, name, role_key in rows
        ],
    }


class _RequestEnhancementBody(BaseModel):
    reviewer_user_ids: list[uuid.UUID] = Field(default_factory=list)


@projects_router.post(
    "/request-enhancement",
    summary="Pull the chosen CEO/Director members onto the script_drafting card and email them",
)
async def post_request_enhancement(
    body: _RequestEnhancementBody,
    project: Annotated[
        ProjectModel, Depends(require_project_access(ProjectAccess.EDIT))
    ],
    user: CurrentUser,
    session: SessionDep,
) -> dict[str, object]:
    if project.owner_id != user.id and not user.is_super_admin:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only the project owner can request feedback"
        )
    try:
        newly_assigned = await script_service.request_enhancement(
            session,
            project=project,
            actor=user,
            reviewer_user_ids=body.reviewer_user_ids,
        )
    except ScriptNotFoundError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except NoEnhancementReviewersError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await session.commit()
    return {
        "status": "requested",
        "newly_assigned_user_ids": [str(u) for u in newly_assigned],
    }


# ---------- lock / unlock ----------


@projects_router.post(
    "/lock",
    response_model=ScriptSummaryPublic,
    summary="Lock the script and advance to casting (`script_versioning.lock` action)",
    dependencies=[Depends(require_action("script_versioning.lock"))],
)
async def post_lock(
    project: Annotated[ProjectModel, Depends(require_project_access(ProjectAccess.VIEW))],
    user: CurrentUser,
    session: SessionDep,
) -> ScriptSummaryPublic:
    try:
        await script_service.lock_script(session, project=project, actor=user)
    except IllegalStageTransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except ScriptLockGateError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await session.commit()
    return await get_summary(project, session)


@projects_router.post(
    "/unlock",
    response_model=ScriptSummaryPublic,
    summary="Clear the script lock (owner-only) and roll the stage back from casting if applicable",
    dependencies=[Depends(require_action("script_versioning.unlock"))],
)
async def post_unlock(
    project: Annotated[ProjectModel, Depends(require_project_access(ProjectAccess.VIEW))],
    user: CurrentUser,
    session: SessionDep,
) -> ScriptSummaryPublic:
    if project.owner_id != user.id and not user.is_super_admin:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only the project owner can unlock the script"
        )
    await script_service.unlock_script(session, project=project, actor=user)
    await session.commit()
    return await get_summary(project, session)


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
