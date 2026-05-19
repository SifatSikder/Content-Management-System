"""FastAPI dependencies for authentication + authorisation.

Routes import these and add them as `Depends(...)`. The permission rules in
this module are the *programmatic* mirror of the matrix in
`project_spec.md §6`; when the spec changes, update both. RLS in Phase 5
will provide defense-in-depth at the DB layer.

Usage:

    @router.post("/projects")
    async def create_project(
        body: CreateProjectBody,
        user: CurrentUser,                                   # any authed user
        # _: Annotated[UserModel, Depends(require_role(Role.CEO))],   # role-gated
    ): ...

    @router.patch("/projects/{project_id}")
    async def update_project(
        project: Annotated[ProjectModel, Depends(require_project_access(ProjectAccess.EDIT))],
        user: CurrentUser,
        ...
    ): ...
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import Annotated

import structlog
from fastapi import Depends, HTTPException, Path, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import InvalidTokenError, decode_access_token
from app.models.base import get_session
from app.models.enums import PipelineStage, Role
from app.models.project import ProjectModel
from app.models.user import UserModel

log = structlog.get_logger(__name__)


class ProjectAccess(StrEnum):
    """Levels of access to a single project.

    VIEW   — can read project + nested resources.
    EDIT   — can mutate project fields and nested resources.
    MANAGE — can move stage, lock/unlock script, delete project.
    """

    VIEW = "view"
    EDIT = "edit"
    MANAGE = "manage"


SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def current_user(request: Request, session: SessionDep) -> UserModel:
    """Resolve the bearer JWT into a `UserModel` or raise 401."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    token = auth_header.split(" ", 1)[1].strip()
    try:
        claims = decode_access_token(token)
    except InvalidTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc

    result = await session.execute(
        select(UserModel).where(
            UserModel.id == claims.sub,
            UserModel.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user


CurrentUser = Annotated[UserModel, Depends(current_user)]


def require_role(*allowed: Role) -> Callable[..., Awaitable[UserModel]]:
    """Factory: build a dependency that 403s if the current user lacks `allowed`."""

    async def _dep(user: CurrentUser) -> UserModel:
        if user.role not in allowed:
            log.warning(
                "permission_denied",
                user_id=str(user.id),
                user_role=user.role.value,
                required_roles=[role.value for role in allowed],
            )
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role")
        return user

    return _dep


def _user_can_access_project(
    user: UserModel, project: ProjectModel, level: ProjectAccess
) -> bool:
    """Pure predicate — no DB or HTTP. Easy to unit-test.

    Encodes spec §6 + the "assigned only" rule for crew (proxied by ownership
    until an explicit assignments table lands).
    """
    if user.role == Role.CEO:
        return True

    if level == ProjectAccess.VIEW:
        # Crew sees only their assigned project; everyone else sees all.
        if user.role == Role.CREW:
            return project.owner_id == user.id
        return True

    if level == ProjectAccess.EDIT:
        if user.role == Role.ASSISTANT_DIRECTOR:
            return True
        if user.role in (Role.JUNIOR_DIRECTOR, Role.EDITOR):
            return project.owner_id == user.id
        return False

    if level == ProjectAccess.MANAGE:
        if user.role == Role.ASSISTANT_DIRECTOR:
            return True
        if user.role == Role.JUNIOR_DIRECTOR:
            return project.owner_id == user.id
        return False

    return False


def require_project_access(level: ProjectAccess) -> Callable[..., Awaitable[ProjectModel]]:
    """Factory: resolve `project_id` path param, 404 / 403, or return the project."""

    async def _dep(
        session: SessionDep,
        user: CurrentUser,
        project_id: Annotated[uuid.UUID, Path()],
    ) -> ProjectModel:
        result = await session.execute(
            select(ProjectModel).where(
                ProjectModel.id == project_id,
                ProjectModel.deleted_at.is_(None),
            )
        )
        project = result.scalar_one_or_none()
        if project is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
        if not _user_can_access_project(user, project, level):
            log.warning(
                "project_access_denied",
                user_id=str(user.id),
                user_role=user.role.value,
                project_id=str(project_id),
                level=level.value,
            )
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient project access")
        return project

    return _dep


def can_user_move_to_stage(
    user: UserModel, project: ProjectModel, target_stage: PipelineStage
) -> bool:
    """Pure predicate — can `user` move `project` to `target_stage`?

    Spec §6: stage moves are restricted to CEO + Assistant Director (always);
    Junior Director on owned/assigned projects; nobody else. Marking a project
    `approved_published` is reserved for CEO alone.
    """
    if target_stage == PipelineStage.APPROVED_PUBLISHED:
        return user.role == Role.CEO

    if user.role in (Role.CEO, Role.ASSISTANT_DIRECTOR):
        return True
    if user.role == Role.JUNIOR_DIRECTOR:
        return project.owner_id == user.id
    return False


__all__ = [
    "CurrentUser",
    "ProjectAccess",
    "SessionDep",
    "can_user_move_to_stage",
    "current_user",
    "require_project_access",
    "require_role",
]
