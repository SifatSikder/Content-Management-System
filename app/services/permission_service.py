"""Permission service — DB-backed answer to "can this user do X?".

Replaces the hardcoded matrix in `app/auth/dependencies.py` from Phase 1.
Authoritative inputs:

  1. `users.role == Role.CEO` short-circuits to True for every check (CEO is
     the global super-admin).
  2. `department_memberships` row (department_id, user_id) → role_id
  3. `department_role_permissions` rows (role_id, action_key) → allowed

Permissions are scoped by **department**, not business. A user may have
different roles (and therefore different action sets) in two departments
of the same business.

Ownership predicates ("can edit projects they own") stay as runtime checks
in this module — they're not expressible as static `(role, action)` triples
without a per-project context.

Per-request caching: the resolved `{action_key: allowed}` map for each
`(user_id, department_id)` is cached on `request.state.permission_cache`,
keyed by the same tuple. Routes that issue several permission checks per
request only pay the SQL cost once.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.department import DepartmentModel
from app.models.department_membership import DepartmentMembershipModel
from app.models.department_role_permission import DepartmentRolePermissionModel
from app.models.project import ProjectModel
from app.models.user import UserModel
from app.services import stage_registry

log = structlog.get_logger(__name__)


# ---------- low-level lookups -----------------------------------------------


def _cache_for_request(request: Request | None) -> dict[tuple[uuid.UUID, uuid.UUID], dict[str, bool]]:
    """Return (and lazily create) the per-request permission cache dict."""
    if request is None:
        return {}
    cache = getattr(request.state, "permission_cache", None)
    if cache is None:
        cache = {}
        request.state.permission_cache = cache
    return cache


async def _load_permission_map(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    department_id: uuid.UUID,
) -> dict[str, bool]:
    """Resolve the `{action_key: allowed}` map for one user in one department.

    Returns an empty dict if the user has no membership in this department
    (which means they have no department-scoped permissions).
    """
    membership_q = await session.execute(
        select(DepartmentMembershipModel).where(
            DepartmentMembershipModel.user_id == user_id,
            DepartmentMembershipModel.department_id == department_id,
        )
    )
    membership = membership_q.scalar_one_or_none()
    if membership is None:
        return {}

    perm_q = await session.execute(
        select(
            DepartmentRolePermissionModel.action_key,
            DepartmentRolePermissionModel.allowed,
        ).where(DepartmentRolePermissionModel.department_role_id == membership.role_id)
    )
    return {action: allowed for action, allowed in perm_q.all()}


async def permissions_for_user(
    session: AsyncSession,
    *,
    user: UserModel,
    department_id: uuid.UUID,
    request: Request | None = None,
) -> dict[str, bool]:
    """Return the resolved `{action_key: allowed}` map.

    For CEO super-admins the map is `{"*": True}` — callers should rely on
    the `can_user_perform_action` helper rather than introspecting this
    dict, but it's surfaced as-is to the frontend so the UI can render
    affordances without a second round-trip.
    """
    if user.is_super_admin:
        return {"*": True}

    cache = _cache_for_request(request)
    key = (user.id, department_id)
    if key in cache:
        return cache[key]

    perms = await _load_permission_map(
        session, user_id=user.id, department_id=department_id
    )
    cache[key] = perms
    return perms


# ---------- public predicates -----------------------------------------------


async def can_user_perform_action(
    session: AsyncSession,
    *,
    user: UserModel,
    department_id: uuid.UUID,
    action_key: str,
    request: Request | None = None,
) -> bool:
    """True iff the user's department role grants `action_key`."""
    if user.is_super_admin:
        return True
    perms = await permissions_for_user(
        session, user=user, department_id=department_id, request=request
    )
    return bool(perms.get(action_key, False))


async def can_user_access_project(
    session: AsyncSession,
    *,
    user: UserModel,
    project: ProjectModel,
    level: str,
    request: Request | None = None,
) -> bool:
    """True if the user can VIEW/EDIT/MANAGE `project` at the requested level.

    Rules (encoded here rather than as static action_keys because they
    involve per-project ownership):

      * CEO super-admin: always True.
      * Project owner: always True (any level).
      * Otherwise: check the user's department role's `project.edit` /
        `project.delete` permission, with VIEW granted to anyone with a
        department membership.

    Phase D dropped the Phase-B-era `_legacy_*` fallbacks. After the B2
    backfill every project carries a `department_id`, and the
    `projects.department_id NOT NULL` constraint from `b3f8c5d1a7e9`
    guarantees it stays that way. If you somehow hit a row without one,
    that's a bug, not a degraded path.
    """
    if user.is_super_admin:
        return True
    if project.owner_id == user.id:
        return True

    perms = await permissions_for_user(
        session, user=user, department_id=project.department_id, request=request
    )

    if level == "view":
        # Membership alone implies view; non-members got an empty dict back.
        return bool(perms) or perms.get("project.view", False)
    if level == "edit":
        return bool(perms.get("project.edit", False))
    if level == "manage":
        return bool(perms.get("project.delete", False))
    return False


async def can_user_move_to_stage(
    session: AsyncSession,
    *,
    user: UserModel,
    project: ProjectModel,
    target_stage_key: str,
    request: Request | None = None,
) -> bool:
    """True if the user may move `project` to `target_stage_key`.

    Looks up the source + target stage keys in the in-code registry for the
    project's department template, then checks the action
    `stage.move:<from>-><to>` on the user's department role.
    """
    if user.is_super_admin:
        return True

    department = await session.get(DepartmentModel, project.department_id)
    if department is None:
        return False
    if not stage_registry.is_known_stage(department.template_key, target_stage_key):
        return False
    if not stage_registry.is_known_stage(department.template_key, project.stage_key):
        return False

    action = f"stage.move:{project.stage_key}->{target_stage_key}"
    base_allowed = await can_user_perform_action(
        session,
        user=user,
        department_id=project.department_id,
        action_key=action,
        request=request,
    )
    if not base_allowed:
        return False

    # Junior-director-style ownership constraint: if the role has the
    # `project.delete` permission they're a full admin of moves; otherwise
    # they're only allowed to move projects they own.
    can_manage = await can_user_perform_action(
        session,
        user=user,
        department_id=project.department_id,
        action_key="project.delete",
        request=request,
    )
    if can_manage:
        return True
    return project.owner_id == user.id


# ---------- department-aware helpers ----------------------------------------


async def get_department(
    session: AsyncSession, department_id: uuid.UUID
) -> DepartmentModel | None:
    return await session.get(DepartmentModel, department_id)


__all__ = [
    "can_user_access_project",
    "can_user_move_to_stage",
    "can_user_perform_action",
    "get_department",
    "permissions_for_user",
]


def serialise_action_map(perms: dict[str, bool]) -> dict[str, Any]:
    """Frontend shape: `{is_super_admin: bool, allowed: {action_key: bool}}`.

    The wildcard key `"*"` is hoisted into `is_super_admin` to make the
    common short-circuit explicit on the wire.
    """
    if perms.get("*", False):
        return {"is_super_admin": True, "allowed": {}}
    return {"is_super_admin": False, "allowed": {k: v for k, v in perms.items() if v}}
