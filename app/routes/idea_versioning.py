"""Draft-idea endpoints — versions, per-reviewer signoffs, and the lock action."""

from __future__ import annotations

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import (
    CurrentUser,
    ProjectAccess,
    SessionDep,
    require_action,
    require_project_access,
)
from app.models.project import ProjectModel
from app.schemas.idea import (
    CreateIdeaSignoffBody,
    CreateIdeaVersionBody,
    IdeaSignoffPublic,
    IdeaSummaryPublic,
    IdeaVersionPublic,
)
from app.services import idea_service
from app.services.idea_service import (
    IdeaAlreadyLockedError,
    IdeaLockGateError,
    IdeaNotFoundError,
    IdeaVersionNotFoundError,
    NoEnhancementReviewersError,
)

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/projects/{project_id}/idea", tags=["idea"])


# ---------- summary ----------


@router.get(
    "",
    response_model=IdeaSummaryPublic,
    summary="Get the project's idea-phase state (latest version + signoffs + lock gate)",
)
async def get_summary(
    project: Annotated[
        ProjectModel, Depends(require_project_access(ProjectAccess.VIEW))
    ],
    session: SessionDep,
) -> IdeaSummaryPublic:
    idea = await idea_service.get_idea(session, project=project)
    latest = await idea_service.latest_version(session, project=project)
    signoffs: list[IdeaSignoffPublic] = []
    if latest is not None:
        rows = await idea_service.list_signoffs(session, version_id=latest.id)
        signoffs = [IdeaSignoffPublic.model_validate(r) for r in rows]
    can_lock, pending = await idea_service.lock_gate_status(
        session, project=project
    )
    return IdeaSummaryPublic(
        locked_at=idea.locked_at if idea else None,
        locked_by=idea.locked_by if idea else None,
        latest_version=IdeaVersionPublic.model_validate(latest) if latest else None,
        latest_version_signoffs=signoffs,
        pending_reviewer_ids=pending,
        can_lock=can_lock,
    )


# ---------- versions ----------


@router.get(
    "/versions",
    response_model=list[IdeaVersionPublic],
    summary="List all idea versions for a project",
)
async def get_versions(
    project: Annotated[
        ProjectModel, Depends(require_project_access(ProjectAccess.VIEW))
    ],
    session: SessionDep,
) -> list[IdeaVersionPublic]:
    rows = await idea_service.list_versions(session, project=project)
    return [IdeaVersionPublic.model_validate(r) for r in rows]


@router.post(
    "/versions",
    response_model=IdeaVersionPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new idea version",
)
async def post_version(
    body: CreateIdeaVersionBody,
    project: Annotated[
        ProjectModel, Depends(require_project_access(ProjectAccess.EDIT))
    ],
    user: CurrentUser,
    session: SessionDep,
) -> IdeaVersionPublic:
    try:
        version = await idea_service.add_version(
            session, project=project, author=user, body_markdown=body.body_markdown
        )
    except IdeaAlreadyLockedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await session.commit()
    await session.refresh(version)
    return IdeaVersionPublic.model_validate(version)


# ---------- signoffs ----------


@router.post(
    "/versions/{version_id}/signoffs",
    response_model=IdeaSignoffPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Sign off on an idea version (idea_versioning.signoff action)",
    dependencies=[Depends(require_action("idea_versioning.signoff"))],
)
async def post_signoff(
    version_id: uuid.UUID,
    body: CreateIdeaSignoffBody,
    project: Annotated[
        ProjectModel, Depends(require_project_access(ProjectAccess.VIEW))
    ],
    user: CurrentUser,
    session: SessionDep,
) -> IdeaSignoffPublic:
    try:
        version = await idea_service.get_version(session, version_id=version_id)
    except IdeaVersionNotFoundError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Idea version not found"
        ) from exc
    row = await idea_service.add_signoff(
        session,
        project=project,
        version=version,
        reviewer=user,
        decision=body.decision,
        comment=body.comment,
    )
    await session.commit()
    await session.refresh(row)
    return IdeaSignoffPublic.model_validate(row)


# ---------- request enhancement ----------


@router.post(
    "/request-enhancement",
    summary="Pull CEO + Director onto the draft_idea card and email them",
)
async def post_request_enhancement(
    project: Annotated[
        ProjectModel, Depends(require_project_access(ProjectAccess.EDIT))
    ],
    user: CurrentUser,
    session: SessionDep,
) -> dict[str, object]:
    # Only the project owner can request feedback. The role-based
    # `project.create` permission isn't enough — multiple Asst CEOs in
    # the same dept shouldn't be able to ping reviewers on each other's
    # projects.
    if project.owner_id != user.id and not user.is_super_admin:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only the project owner can request feedback"
        )
    try:
        newly_assigned = await idea_service.request_enhancement(
            session, project=project, actor=user
        )
    except IdeaNotFoundError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except NoEnhancementReviewersError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await session.commit()
    return {
        "status": "requested",
        "newly_assigned_user_ids": [str(u) for u in newly_assigned],
    }


# ---------- lock ----------


@router.post(
    "/lock",
    response_model=IdeaSummaryPublic,
    summary="Lock the idea and advance the project (idea_versioning.lock action)",
    dependencies=[Depends(require_action("idea_versioning.lock"))],
)
async def post_lock(
    project: Annotated[
        ProjectModel, Depends(require_project_access(ProjectAccess.VIEW))
    ],
    user: CurrentUser,
    session: SessionDep,
) -> IdeaSummaryPublic:
    try:
        await idea_service.lock_idea(session, project=project, actor=user)
    except IdeaNotFoundError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except IdeaLockGateError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await session.commit()
    # Return the post-lock summary so the UI can update in one round-trip.
    return await get_summary(project, session)


__all__ = ["router"]
