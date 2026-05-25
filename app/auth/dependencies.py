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
from app.core.business_context import business_scoped_session
from app.models.business import BusinessModel
from app.models.business_membership import BusinessMembershipModel
from app.models.enums import BusinessMembershipStatus, Role
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


SessionDep = Annotated[AsyncSession, Depends(business_scoped_session)]


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


async def _user_can_access_project(
    session: AsyncSession,
    user: UserModel,
    project: ProjectModel,
    level: ProjectAccess,
    *,
    request: Request | None = None,
) -> bool:
    """Thin shim that routes the legacy access check through
    `permission_service.can_user_access_project`.

    The signature keeps the same call sites that already pass
    `(user, project, level)` — they now also pass `session` + the optional
    `request`. Most callers are already inside an `async def` with both in
    scope, so the migration cost is per-callsite-one-line.
    """
    from app.services import permission_service

    return await permission_service.can_user_access_project(
        session,
        user=user,
        project=project,
        level=level.value,
        request=request,
    )


def require_project_access(level: ProjectAccess) -> Callable[..., Awaitable[ProjectModel]]:
    """Factory: resolve `project_id` path param, 404 / 403, or return the project."""

    async def _dep(
        request: Request,
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
        allowed = await _user_can_access_project(
            session, user, project, level, request=request
        )
        if not allowed:
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


async def can_user_move_to_stage(
    session: AsyncSession,
    user: UserModel,
    project: ProjectModel,
    target_stage_id: uuid.UUID,
    *,
    request: Request | None = None,
) -> bool:
    """Async wrapper around `permission_service.can_user_move_to_stage`.

    Kept here for the same reason the access shim above is — callers that
    haven't been refactored to import `permission_service` directly can
    keep going through this module.
    """
    from app.services import permission_service

    return await permission_service.can_user_move_to_stage(
        session,
        user=user,
        project=project,
        target_stage_id=target_stage_id,
        request=request,
    )


async def require_business_member(
    session: SessionDep,
    user: CurrentUser,
    business_id: Annotated[uuid.UUID, Path()],
) -> BusinessMembershipModel | None:
    """403 unless the current user is the CEO or an active member.

    Returns `None` for the CEO (super-admin) — callers should not rely on
    the return value beyond `Depends(...)`-style gating. The path parameter
    must literally be named `business_id`.
    """
    if user.is_super_admin:
        return None
    result = await session.execute(
        select(BusinessMembershipModel).where(
            BusinessMembershipModel.business_id == business_id,
            BusinessMembershipModel.user_id == user.id,
            BusinessMembershipModel.status == BusinessMembershipStatus.ACTIVE,
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        log.warning(
            "business_member_required_denied",
            user_id=str(user.id),
            business_id=str(business_id),
        )
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Not a member of this business"
        )
    return membership


async def require_business_admin(
    session: SessionDep,
    user: CurrentUser,
    business_id: Annotated[uuid.UUID, Path()],
) -> BusinessModel:
    """403 unless the user is the CEO or the business's owner.

    Returns the `BusinessModel` row so the route handler can reuse it
    without a second lookup. The path parameter must literally be named
    `business_id`.
    """
    result = await session.execute(
        select(BusinessModel).where(
            BusinessModel.id == business_id,
            BusinessModel.deleted_at.is_(None),
        )
    )
    business = result.scalar_one_or_none()
    if business is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Business not found")
    if not user.is_super_admin and business.owner_user_id != user.id:
        log.warning(
            "business_admin_required_denied",
            user_id=str(user.id),
            business_id=str(business_id),
        )
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Business admin only")
    return business


__all__ = [
    "CurrentUser",
    "ProjectAccess",
    "SessionDep",
    "can_user_move_to_stage",
    "current_user",
    "require_business_admin",
    "require_business_member",
    "require_project_access",
    "require_role",
]
