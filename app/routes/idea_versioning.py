"""Draft-idea endpoints — versions, per-reviewer signoffs, and the lock action."""

from __future__ import annotations

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.auth.dependencies import (
    CurrentUser,
    ProjectAccess,
    SessionDep,
    require_action,
    require_project_access,
)
from app.models.project import ProjectModel
from app.models.user import UserModel
from app.schemas.idea import (
    CreateIdeaSignoffBody,
    CreateIdeaVersionBody,
    IdeaSignoffPublic,
    IdeaSummaryPublic,
    IdeaVersionPublic,
    UpdateIdeaVersionBody,
)
from app.services import idea_service
from app.services.idea_service import (
    IdeaAlreadyLockedError,
    IdeaLockGateError,
    IdeaNotFoundError,
    IdeaVersionNotEditableError,
    IdeaVersionNotFoundError,
    IdeaVersionNotSubmittedError,
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
    reviewer_count = await idea_service.reviewer_count(
        session, project=project
    )
    return IdeaSummaryPublic(
        locked_at=idea.locked_at if idea else None,
        locked_by=idea.locked_by if idea else None,
        latest_version=IdeaVersionPublic.model_validate(latest) if latest else None,
        latest_version_signoffs=signoffs,
        pending_reviewer_ids=pending,
        can_lock=can_lock,
        reviewer_count=reviewer_count,
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
    # Owner-only — reviewers (CEO/Director) only sign off; they don't
    # draft new versions. Matches the patch + request-enhancement guards.
    if project.owner_id != user.id and not user.is_super_admin:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only the project owner can draft a new idea version",
        )
    try:
        version = await idea_service.add_version(
            session, project=project, author=user, body_markdown=body.body_markdown
        )
    except IdeaAlreadyLockedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await session.commit()
    await session.refresh(version)
    return IdeaVersionPublic.model_validate(version)


@router.patch(
    "/versions/{version_id}",
    response_model=IdeaVersionPublic,
    summary="Edit the current version body in place (owner-only, pre-feedback)",
)
async def patch_version(
    version_id: uuid.UUID,
    body: UpdateIdeaVersionBody,
    project: Annotated[
        ProjectModel, Depends(require_project_access(ProjectAccess.EDIT))
    ],
    user: CurrentUser,
    session: SessionDep,
) -> IdeaVersionPublic:
    if project.owner_id != user.id and not user.is_super_admin:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only the project owner can edit the draft"
        )
    try:
        version = await idea_service.get_version(session, version_id=version_id)
    except IdeaVersionNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Idea version not found") from exc
    try:
        await idea_service.update_version_body(
            session,
            project=project,
            version=version,
            actor=user,
            body_markdown=body.body_markdown,
        )
    except IdeaVersionNotEditableError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await session.commit()
    await session.refresh(version)
    return IdeaVersionPublic.model_validate(version)


# ---------- signoffs ----------


@router.get(
    "/versions/{version_id}/signoffs",
    response_model=list[IdeaSignoffPublic],
    summary="List signoffs for one specific idea version",
)
async def get_signoffs(
    version_id: uuid.UUID,
    project: Annotated[
        ProjectModel, Depends(require_project_access(ProjectAccess.VIEW))
    ],
    session: SessionDep,
) -> list[IdeaSignoffPublic]:
    # Verify the version actually belongs to this project's idea so a
    # random version_id from another project can't be probed inside the
    # same business.
    try:
        version = await idea_service.get_version(session, version_id=version_id)
    except IdeaVersionNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Idea version not found") from exc
    idea = await idea_service.get_idea(session, project=project)
    if idea is None or version.idea_id != idea.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Idea version not found")
    rows = await idea_service.list_signoffs(session, version_id=version_id)
    # Resolve reviewer display info in one go — the version history UI
    # would otherwise have to fall back on department memberships, and
    # super-admins (CEO) may sign off without ever having a membership
    # row in this department.
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
    out: list[IdeaSignoffPublic] = []
    for r in rows:
        info = name_by_id.get(r.reviewer_id)
        out.append(
            IdeaSignoffPublic.model_validate(
                {
                    "id": r.id,
                    "idea_version_id": r.idea_version_id,
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
    try:
        row = await idea_service.add_signoff(
            session,
            project=project,
            version=version,
            reviewer=user,
            decision=body.decision,
            comment=body.comment,
        )
    except IdeaVersionNotSubmittedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await session.commit()
    await session.refresh(row)
    return IdeaSignoffPublic.model_validate(row)


# ---------- request enhancement ----------


@router.get(
    "/enhancement-candidates",
    summary="List CEO + Director members the owner can ask for feedback",
)
async def get_enhancement_candidates(
    project: Annotated[
        ProjectModel, Depends(require_project_access(ProjectAccess.VIEW))
    ],
    session: SessionDep,
) -> dict[str, list[dict[str, str | None]]]:
    rows = await idea_service.list_enhancement_candidates(
        session, project=project
    )
    latest = await idea_service.latest_signoff_decision_by_user(
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


@router.post(
    "/request-enhancement",
    summary="Pull the chosen CEO/Director members onto the draft_idea card and email them",
)
async def post_request_enhancement(
    body: _RequestEnhancementBody,
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
            session,
            project=project,
            actor=user,
            reviewer_user_ids=body.reviewer_user_ids,
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


@router.post(
    "/unlock",
    response_model=IdeaSummaryPublic,
    summary="Clear the idea lock so the owner can edit / re-version",
    dependencies=[Depends(require_action("idea_versioning.lock"))],
)
async def post_unlock(
    project: Annotated[
        ProjectModel, Depends(require_project_access(ProjectAccess.VIEW))
    ],
    user: CurrentUser,
    session: SessionDep,
) -> IdeaSummaryPublic:
    # Owner-only — mirrors the location unlock semantics. The Asst CEO
    # owns the draft and is the only one who should be able to reopen it.
    if project.owner_id != user.id and not user.is_super_admin:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only the project owner can unlock the idea"
        )
    await idea_service.unlock_idea(session, project=project, actor=user)
    await session.commit()
    return await get_summary(project, session)


__all__ = ["router"]
