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
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business_membership import BusinessMembershipModel
from app.models.department import DepartmentModel
from app.models.department_membership import DepartmentMembershipModel
from app.models.department_role import DepartmentRoleModel
from app.models.department_role_permission import DepartmentRolePermissionModel
from app.models.department_stage import DepartmentStageModel
from app.models.department_template import DepartmentTemplateModel
from app.models.enums import BusinessMembershipStatus
from app.models.project import ProjectModel

log = structlog.get_logger(__name__)


class DepartmentNotFoundError(Exception):
    """Department does not exist."""


class StageNotFoundError(Exception):
    """Department stage does not exist."""


class StageInUseError(Exception):
    """A project still references this stage; refuse to delete."""


class RoleNotFoundError(Exception):
    """Department role does not exist."""


class TemplateNotFoundError(Exception):
    """Department template key does not exist."""


class SlugTakenError(Exception):
    """Another department already uses this slug in the business."""


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

    capabilities: list[str] = []
    capability_configs: dict[str, dict[str, Any]] = {}
    terminology: dict[str, dict[str, str]] = {}
    seed_stages: list[dict[str, Any]] = []
    seed_roles: list[dict[str, Any]] = []
    seed_role_permissions: list[dict[str, Any]] = []
    if template_key is not None:
        template = await _load_template(session, key=template_key)
        capabilities = list(template.default_capabilities or [])
        # Copy per-capability config + terminology so later template edits
        # don't retroactively mutate live departments.
        capability_configs = dict(
            getattr(template, "default_capability_configs", None) or {}
        )
        terminology = dict(getattr(template, "default_terminology", None) or {})
        seed_stages = list(template.default_stages or [])
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
        capabilities=capabilities,
        capability_configs=capability_configs,
        terminology=terminology,
    )
    session.add(department)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise SlugTakenError(candidate) from exc

    # First pass: create stages without resolving cross-stage references.
    stage_id_by_key: dict[str, uuid.UUID] = {}
    stages_pending_resolution: list[tuple[DepartmentStageModel, list[str]]] = []
    for idx, raw in enumerate(seed_stages):
        key = raw.get("key") or f"stage-{idx}"
        # Templates carry `allowed_from_stage_keys` (string keys); live rows
        # store ids. Keep `allowed_from_stage_ids` accepted for backwards
        # compatibility (Phase A path passes ids directly).
        allowed_keys = raw.get("allowed_from_stage_keys")
        if allowed_keys is None:
            preset_ids = raw.get("allowed_from_stage_ids", [])
            allowed_ids: list[str] = [str(sid) for sid in preset_ids]
            allowed_keys_pending: list[str] = []
        else:
            allowed_ids = []
            allowed_keys_pending = list(allowed_keys)

        stage = DepartmentStageModel(
            department_id=department.id,
            business_id=business_id,
            key=key,
            name_i18n=raw.get("name_i18n") or {},
            order_index=raw.get("order_index", idx),
            is_terminal=bool(raw.get("is_terminal", False)),
            color=raw.get("color"),
            allowed_from_stage_ids=allowed_ids,
        )
        session.add(stage)
        stages_pending_resolution.append((stage, allowed_keys_pending))
    await session.flush()
    for stage, _ in stages_pending_resolution:
        stage_id_by_key[stage.key] = stage.id

    # Second pass: resolve allowed_from_stage_keys → ids now that every
    # sibling stage has an id.
    for stage, pending_keys in stages_pending_resolution:
        if not pending_keys:
            continue
        resolved = [
            str(stage_id_by_key[k]) for k in pending_keys if k in stage_id_by_key
        ]
        stage.allowed_from_stage_ids = resolved

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
    capabilities: list[str] | None = None,
) -> DepartmentModel:
    if name is not None and name != department.name:
        department.name = name
    if capabilities is not None:
        department.capabilities = list(capabilities)
    await session.flush()
    return department


async def archive_department(
    session: AsyncSession, *, department: DepartmentModel
) -> DepartmentModel:
    if department.archived_at is None:
        department.archived_at = datetime.now(UTC)
        await session.flush()
    return department


# --- Stages --------------------------------------------------------------


async def list_stages(
    session: AsyncSession, *, department_id: uuid.UUID
) -> Sequence[DepartmentStageModel]:
    result = await session.execute(
        select(DepartmentStageModel)
        .where(DepartmentStageModel.department_id == department_id)
        .order_by(DepartmentStageModel.order_index.asc())
    )
    return result.scalars().all()


async def create_stage(
    session: AsyncSession,
    *,
    department: DepartmentModel,
    key: str,
    name_i18n: dict[str, str],
    order_index: int = 0,
    is_terminal: bool = False,
    color: str | None = None,
    allowed_from_stage_ids: list[uuid.UUID] | None = None,
) -> DepartmentStageModel:
    stage = DepartmentStageModel(
        department_id=department.id,
        business_id=department.business_id,
        key=key,
        name_i18n=name_i18n,
        order_index=order_index,
        is_terminal=is_terminal,
        color=color,
        allowed_from_stage_ids=[str(sid) for sid in (allowed_from_stage_ids or [])],
    )
    session.add(stage)
    await session.flush()
    return stage


async def get_stage(
    session: AsyncSession, *, stage_id: uuid.UUID
) -> DepartmentStageModel:
    stage = await session.get(DepartmentStageModel, stage_id)
    if stage is None:
        raise StageNotFoundError(str(stage_id))
    return stage


async def update_stage(
    session: AsyncSession,
    *,
    stage: DepartmentStageModel,
    name_i18n: dict[str, str] | None = None,
    order_index: int | None = None,
    is_terminal: bool | None = None,
    color: str | None = None,
    allowed_from_stage_ids: list[uuid.UUID] | None = None,
) -> DepartmentStageModel:
    if name_i18n is not None:
        stage.name_i18n = dict(name_i18n)
    if order_index is not None:
        stage.order_index = order_index
    if is_terminal is not None:
        stage.is_terminal = is_terminal
    if color is not None:
        stage.color = color
    if allowed_from_stage_ids is not None:
        stage.allowed_from_stage_ids = [str(sid) for sid in allowed_from_stage_ids]
    await session.flush()
    return stage


async def delete_stage(
    session: AsyncSession, *, stage: DepartmentStageModel
) -> None:
    # Refuse to delete if any project still references this stage_id.
    in_use = await session.execute(
        select(ProjectModel.id).where(ProjectModel.stage_id == stage.id).limit(1)
    )
    if in_use.first() is not None:
        raise StageInUseError(str(stage.id))
    await session.delete(stage)
    await session.flush()


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
    the business-level row. If one already exists in any non-revoked state
    we leave it alone. A previously-revoked row is reactivated.
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
        return
    if existing.status != BusinessMembershipStatus.ACTIVE:
        existing.status = BusinessMembershipStatus.ACTIVE
        existing.joined_at = existing.joined_at or datetime.now(UTC)
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
    "RoleNotFoundError",
    "SlugTakenError",
    "StageInUseError",
    "StageNotFoundError",
    "TemplateNotFoundError",
    "archive_department",
    "assign_department_member",
    "create_department",
    "create_role",
    "create_stage",
    "delete_role",
    "delete_stage",
    "get_department",
    "get_role",
    "get_stage",
    "list_department_memberships",
    "list_departments",
    "list_permissions",
    "list_roles",
    "list_stages",
    "remove_department_member",
    "slugify",
    "update_department",
    "update_role",
    "update_stage",
    "upsert_permission",
]
