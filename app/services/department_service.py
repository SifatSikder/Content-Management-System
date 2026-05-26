"""Department, stage, role, permission, and membership services.

All functions are pure (no FastAPI). The CEO super-admin and the
business owner can mutate everything; regular members are read-only.
Authorisation is enforced by the route layer via the new
`require_business_admin` / `require_business_member` dependencies.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business_membership import BusinessMembershipModel
from app.models.department import DepartmentModel
from app.models.department_membership import DepartmentMembershipModel
from app.models.department_role import DepartmentRoleModel
from app.models.department_role_permission import DepartmentRolePermissionModel
from app.models.department_template import DepartmentTemplateModel
from app.models.enums import BusinessMembershipStatus

log = structlog.get_logger(__name__)


class DepartmentNotFoundError(Exception):
    """Department does not exist."""


class RoleNotFoundError(Exception):
    """Department role does not exist."""


class TemplateNotFoundError(Exception):
    """Department template key does not exist."""


class SlugTakenError(Exception):
    """Another department already uses this slug in the business."""


class RoleInUseError(Exception):
    """Role still has member assignments and cannot be deleted."""

    def __init__(self, role_id: uuid.UUID, member_count: int) -> None:
        super().__init__(
            f"role {role_id} has {member_count} member(s); reassign them before deleting"
        )
        self.role_id = role_id
        self.member_count = member_count


_SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")
_SLUG_TRIM_RE = re.compile(r"^-+|-+$")


def slugify(name: str) -> str:
    lowered = name.strip().lower()
    slug = _SLUG_STRIP_RE.sub("-", lowered)
    slug = _SLUG_TRIM_RE.sub("", slug)
    return slug or "department"


async def _slug_taken(
    session: AsyncSession, *, business_id: uuid.UUID, slug: str
) -> bool:
    result = await session.execute(
        select(DepartmentModel.id).where(
            DepartmentModel.business_id == business_id,
            DepartmentModel.slug == slug,
        )
    )
    return result.first() is not None


# --- Templates -----------------------------------------------------------


async def _load_template(
    session: AsyncSession, *, key: str
) -> DepartmentTemplateModel:
    result = await session.execute(
        select(DepartmentTemplateModel).where(DepartmentTemplateModel.key == key)
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise TemplateNotFoundError(key)
    return template


def _load_role_permissions_from_python(template_key: str) -> list[dict[str, Any]]:
    """Read `default_role_permissions` from the registered Python template.

    Phase B's migration writes templates into `department_templates` without
    a `default_role_permissions` column — the permission triples are too
    structured to round-trip as JSONB without schema work, and the Phase B
    data migration seeded them directly from the Python source. This helper
    keeps `create_department` consistent with that pattern: the Python
    template is the authoritative source for permission triples.

    Returns an empty list if the template key isn't registered (e.g. a
    user-created template that we don't ship code for).
    """
    try:
        from app.seeds.templates import get_template
    except ImportError:
        return []
    try:
        tpl = get_template(template_key)
    except KeyError:
        return []
    return list(tpl.get("default_role_permissions", []) or [])


# --- Departments ---------------------------------------------------------


async def create_department(
    session: AsyncSession,
    *,
    business_id: uuid.UUID,
    name: str,
    slug: str | None = None,
    template_key: str | None = None,
) -> DepartmentModel:
    """Create a department, optionally hydrating from a template's defaults."""
    base_slug = slug or slugify(name)
    candidate = base_slug
    counter = 1
    while await _slug_taken(session, business_id=business_id, slug=candidate):
        counter += 1
        candidate = f"{base_slug}-{counter}"

    terminology: dict[str, dict[str, str]] = {}
    seed_roles: list[dict[str, Any]] = []
    seed_role_permissions: list[dict[str, Any]] = []
    if template_key is not None:
        template = await _load_template(session, key=template_key)
        # Copy terminology so later template edits don't retroactively
        # mutate live departments.
        terminology = dict(getattr(template, "default_terminology", None) or {})
        seed_roles = list(template.default_roles or [])
        # Permissions are NOT a column on `department_templates` (Phase B's
        # migration didn't add one — the data migration there inlined the
        # permission seed by reading the Python source directly). For
        # `create_department` calls outside that migration we fall back to
        # the registered Python template, which is the authoritative source.
        seed_role_permissions = _load_role_permissions_from_python(template_key)

    department = DepartmentModel(
        business_id=business_id,
        template_key=template_key,
        name=name,
        slug=candidate,
        terminology=terminology,
    )
    session.add(department)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise SlugTakenError(candidate) from exc

    # Stages are no longer copied into the DB — `stage_registry` resolves
    # them from `app/seeds/templates/<key>.py::STAGES` at runtime per
    # `template_key`. See `app/services/stage_registry.py`.

    # Roles.
    role_id_by_key: dict[str, uuid.UUID] = {}
    for raw in seed_roles:
        role_key = raw.get("key") or "member"
        role = DepartmentRoleModel(
            department_id=department.id,
            business_id=business_id,
            key=role_key,
            name_i18n=raw.get("name_i18n") or {},
            description=raw.get("description"),
        )
        session.add(role)
        await session.flush()
        role_id_by_key[role_key] = role.id

    # Permissions — only the explicit `allowed=True` rows go in; absence
    # means "denied" at lookup time.
    for raw in seed_role_permissions:
        role_key = raw.get("role_key")
        action_key = raw.get("action_key")
        if not role_key or not action_key:
            continue
        role_id = role_id_by_key.get(role_key)
        if role_id is None:
            continue
        session.add(
            DepartmentRolePermissionModel(
                department_role_id=role_id,
                business_id=business_id,
                action_key=action_key,
                allowed=bool(raw.get("allowed", False)),
            )
        )

    await session.flush()
    return department


async def list_departments(
    session: AsyncSession,
    *,
    business_id: uuid.UUID,
    include_archived: bool = False,
) -> Sequence[DepartmentModel]:
    where = [DepartmentModel.business_id == business_id]
    if not include_archived:
        where.append(DepartmentModel.archived_at.is_(None))
    result = await session.execute(
        select(DepartmentModel)
        .where(*where)
        .order_by(DepartmentModel.created_at.asc())
    )
    return result.scalars().all()


async def get_department(
    session: AsyncSession, *, department_id: uuid.UUID
) -> DepartmentModel:
    department = await session.get(DepartmentModel, department_id)
    if department is None:
        raise DepartmentNotFoundError(str(department_id))
    return department


async def update_department(
    session: AsyncSession,
    *,
    department: DepartmentModel,
    name: str | None = None,
) -> DepartmentModel:
    if name is not None and name != department.name:
        department.name = name
    await session.flush()
    return department


async def archive_department(
    session: AsyncSession, *, department: DepartmentModel
) -> DepartmentModel:
    if department.archived_at is None:
        department.archived_at = datetime.now(UTC)
        await session.flush()
    return department


# --- Roles ---------------------------------------------------------------


async def list_roles(
    session: AsyncSession, *, department_id: uuid.UUID
) -> Sequence[DepartmentRoleModel]:
    result = await session.execute(
        select(DepartmentRoleModel)
        .where(DepartmentRoleModel.department_id == department_id)
        .order_by(DepartmentRoleModel.created_at.asc())
    )
    return result.scalars().all()


async def create_role(
    session: AsyncSession,
    *,
    department: DepartmentModel,
    key: str,
    name_i18n: dict[str, str],
    description: str | None = None,
) -> DepartmentRoleModel:
    role = DepartmentRoleModel(
        department_id=department.id,
        business_id=department.business_id,
        key=key,
        name_i18n=name_i18n,
        description=description,
    )
    session.add(role)
    await session.flush()
    return role


async def get_role(
    session: AsyncSession, *, role_id: uuid.UUID
) -> DepartmentRoleModel:
    role = await session.get(DepartmentRoleModel, role_id)
    if role is None:
        raise RoleNotFoundError(str(role_id))
    return role


async def update_role(
    session: AsyncSession,
    *,
    role: DepartmentRoleModel,
    name_i18n: dict[str, str] | None = None,
    description: str | None = None,
) -> DepartmentRoleModel:
    if name_i18n is not None:
        role.name_i18n = dict(name_i18n)
    if description is not None:
        role.description = description
    await session.flush()
    return role


async def delete_role(
    session: AsyncSession, *, role: DepartmentRoleModel
) -> None:
    member_count = await session.scalar(
        select(func.count())
        .select_from(DepartmentMembershipModel)
        .where(DepartmentMembershipModel.role_id == role.id)
    )
    if member_count:
        raise RoleInUseError(role.id, int(member_count))
    await session.delete(role)
    await session.flush()


# --- Permissions ---------------------------------------------------------


async def list_permissions(
    session: AsyncSession, *, department_role_id: uuid.UUID
) -> Sequence[DepartmentRolePermissionModel]:
    result = await session.execute(
        select(DepartmentRolePermissionModel)
        .where(DepartmentRolePermissionModel.department_role_id == department_role_id)
        .order_by(DepartmentRolePermissionModel.action_key.asc())
    )
    return result.scalars().all()


async def upsert_permission(
    session: AsyncSession,
    *,
    role: DepartmentRoleModel,
    action_key: str,
    allowed: bool,
) -> DepartmentRolePermissionModel:
    result = await session.execute(
        select(DepartmentRolePermissionModel).where(
            DepartmentRolePermissionModel.department_role_id == role.id,
            DepartmentRolePermissionModel.action_key == action_key,
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        existing.allowed = allowed
        await session.flush()
        return existing
    perm = DepartmentRolePermissionModel(
        department_role_id=role.id,
        business_id=role.business_id,
        action_key=action_key,
        allowed=allowed,
    )
    session.add(perm)
    await session.flush()
    return perm


# --- Department memberships ---------------------------------------------


async def list_department_memberships(
    session: AsyncSession, *, department_id: uuid.UUID
) -> Sequence[DepartmentMembershipModel]:
    from sqlalchemy.orm import selectinload

    result = await session.execute(
        select(DepartmentMembershipModel)
        .options(
            selectinload(DepartmentMembershipModel.user),
            selectinload(DepartmentMembershipModel.role),
            selectinload(DepartmentMembershipModel.business_membership),
        )
        .where(DepartmentMembershipModel.department_id == department_id)
        .order_by(DepartmentMembershipModel.created_at.asc())
    )
    return result.scalars().all()


async def _ensure_business_membership(
    session: AsyncSession,
    *,
    business_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Idempotently grant `user_id` a business membership in `business_id`.

    Business memberships are auto-managed off department memberships: as
    soon as a user is assigned to any department in a business, they get
    the business-level row.

    A previously-revoked row is **not** auto-flipped back to active —
    re-activation is an explicit admin action (PATCH on the business
    membership). Adding a revoked user to a new department writes the
    department-membership row but keeps them blocked at the business
    gate until someone toggles them back to Active.
    """
    existing_q = await session.execute(
        select(BusinessMembershipModel).where(
            BusinessMembershipModel.business_id == business_id,
            BusinessMembershipModel.user_id == user_id,
        )
    )
    existing = existing_q.scalar_one_or_none()
    if existing is None:
        session.add(
            BusinessMembershipModel(
                business_id=business_id,
                user_id=user_id,
                status=BusinessMembershipStatus.ACTIVE,
                joined_at=datetime.now(UTC),
            )
        )
        await session.flush()


async def _revoke_business_membership_if_orphan(
    session: AsyncSession,
    *,
    business_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Delete the user's business membership if they have no department
    memberships left in this business.

    Counterpart to `_ensure_business_membership`: removing the user's last
    department assignment in a business should also revoke their
    business-level entry permit. The CEO never has membership rows
    (super-admin bypass) so they're unaffected.
    """
    remaining_q = await session.execute(
        select(DepartmentMembershipModel.id)
        .where(
            DepartmentMembershipModel.business_id == business_id,
            DepartmentMembershipModel.user_id == user_id,
        )
        .limit(1)
    )
    if remaining_q.first() is not None:
        return
    bm_q = await session.execute(
        select(BusinessMembershipModel).where(
            BusinessMembershipModel.business_id == business_id,
            BusinessMembershipModel.user_id == user_id,
        )
    )
    bm = bm_q.scalar_one_or_none()
    if bm is not None:
        await session.delete(bm)
        await session.flush()


async def assign_department_member(
    session: AsyncSession,
    *,
    department: DepartmentModel,
    user_id: uuid.UUID,
    role_id: uuid.UUID,
) -> DepartmentMembershipModel:
    # Ensure the user has the prerequisite business membership. Idempotent.
    await _ensure_business_membership(
        session, business_id=department.business_id, user_id=user_id
    )

    # Re-use the existing row if the user is already a member of the
    # department — update their role instead of duplicating.
    result = await session.execute(
        select(DepartmentMembershipModel).where(
            DepartmentMembershipModel.department_id == department.id,
            DepartmentMembershipModel.user_id == user_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        existing.role_id = role_id
        await session.flush()
        return existing

    membership = DepartmentMembershipModel(
        department_id=department.id,
        business_id=department.business_id,
        user_id=user_id,
        role_id=role_id,
    )
    session.add(membership)
    await session.flush()
    return membership


async def remove_department_member(
    session: AsyncSession, *, membership_id: uuid.UUID, department_id: uuid.UUID
) -> None:
    result = await session.execute(
        select(DepartmentMembershipModel).where(
            DepartmentMembershipModel.id == membership_id,
            DepartmentMembershipModel.department_id == department_id,
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise DepartmentNotFoundError(f"membership {membership_id}")
    business_id = membership.business_id
    user_id = membership.user_id
    await session.delete(membership)
    await session.flush()
    # Auto-revoke the business membership if this was the user's last
    # department in the business.
    await _revoke_business_membership_if_orphan(
        session, business_id=business_id, user_id=user_id
    )


__all__ = [
    "DepartmentNotFoundError",
    "RoleInUseError",
    "RoleNotFoundError",
    "SlugTakenError",
    "TemplateNotFoundError",
    "archive_department",
    "assign_department_member",
    "create_department",
    "create_role",
    "delete_role",
    "get_department",
    "get_role",
    "list_department_memberships",
    "list_departments",
    "list_permissions",
    "list_roles",
    "remove_department_member",
    "slugify",
    "update_department",
    "update_role",
    "upsert_permission",
]
