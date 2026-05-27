"""Project domain service.

Pure business logic — no FastAPI imports. Each mutating method logs an
activity entry; the caller owns the transaction.

Cursor pagination: cursors are opaque base64 strings encoding
`<created_at_iso>|<uuid>`. The list query orders by `(created_at DESC, id DESC)`
and uses the cursor as a `(created_at, id) <` filter for stability across
inserts.

Stages are not a DB table — see `app.services.stage_registry`. Projects
store a `stage_key` string and the registry resolves it against the
department's `template_key`.
"""

from __future__ import annotations

import base64
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

import structlog
from sqlalchemy import ColumnElement, and_, distinct, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.department import DepartmentModel
from app.models.department_membership import DepartmentMembershipModel
from app.models.department_role import DepartmentRoleModel
from app.models.department_role_permission import DepartmentRolePermissionModel
from app.models.enums import Category, Role
from app.models.project import ProjectModel
from app.models.project_stage_assignment import ProjectStageAssignmentModel
from app.models.user import UserModel
from app.services import activity_service, assignment_service, stage_registry

log = structlog.get_logger(__name__)

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100


class ProjectNotFoundError(Exception):
    """Project does not exist (or is soft-deleted when not requested)."""


class InvalidCursorError(Exception):
    """Pagination cursor failed to decode."""


class StageNotFoundError(Exception):
    """No stage with the given key exists in the project's template."""


@dataclass(frozen=True)
class ListFilters:
    stage_key: str | None = None
    owner_id: uuid.UUID | None = None
    mine: bool = False
    include_deleted: bool = False


def _encode_cursor(project: ProjectModel) -> str:
    raw = f"{project.created_at.isoformat()}|{project.id}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        iso, id_str = raw.split("|", 1)
        return datetime.fromisoformat(iso), uuid.UUID(id_str)
    except (ValueError, UnicodeDecodeError) as exc:
        raise InvalidCursorError(f"Invalid cursor: {cursor!r}") from exc


async def _entry_stage_key(
    session: AsyncSession, *, department_id: uuid.UUID
) -> str:
    """Return the first stage key for the department's template.

    Raises if the department has no template or the template has no stages
    — that's a misconfiguration.
    """
    department = await session.get(DepartmentModel, department_id)
    if department is None:
        raise StageNotFoundError(f"Department {department_id} not found")
    stage_key = stage_registry.first_stage_key(department.template_key)
    if stage_key is None:
        raise StageNotFoundError(
            f"Department {department_id} (template={department.template_key!r}) "
            "has no stages — cannot create a project"
        )
    return stage_key


async def create_project(
    session: AsyncSession,
    *,
    actor: UserModel,
    title: str,
    category: Category,
    business_id: uuid.UUID,
    department_id: uuid.UUID,
    description: str | None = None,
    due_date: object | None = None,
    owner_id_override: uuid.UUID | None = None,
    stage_key: str | None = None,
) -> ProjectModel:
    """Create a project. Activity row + commit are the caller's responsibility.

    `stage_key` defaults to the department template's entry stage (first in
    the registry list) so the caller doesn't have to know which one that is.
    """
    owner = actor
    if owner_id_override is not None and actor.role in (Role.CEO, Role.ASSISTANT_DIRECTOR):
        override = await session.get(UserModel, owner_id_override)
        if override is None:
            raise ProjectNotFoundError(f"owner_id_override {owner_id_override} not found")
        owner = override

    if stage_key is None:
        stage_key = await _entry_stage_key(session, department_id=department_id)
    else:
        department = await session.get(DepartmentModel, department_id)
        if department is None or not stage_registry.is_known_stage(
            department.template_key, stage_key
        ):
            raise StageNotFoundError(
                f"Stage {stage_key!r} not in template for department {department_id}"
            )

    project = ProjectModel(
        title=title,
        description=description,
        category=category,
        business_id=business_id,
        department_id=department_id,
        stage_key=stage_key,
        owner=owner,
        due_date=due_date,
    )
    session.add(project)
    await session.flush()
    # Eager-load the department so callers can read `project.department`
    # immediately after creation without an extra refresh.
    await session.refresh(project, attribute_names=["department"])

    await activity_service.record(
        session,
        project_id=project.id,
        actor_id=actor.id,
        action="project.created",
        metadata={"title": title, "category": category.value},
    )
    # Seed the first stage's default assignees (Phase 2 = owner).
    await assignment_service.seed_default(
        session, project=project, stage_key=project.stage_key, actor=actor
    )
    return project


async def get_project(
    session: AsyncSession, *, project_id: uuid.UUID, include_deleted: bool = False
) -> ProjectModel:
    where = [ProjectModel.id == project_id]
    if not include_deleted:
        where.append(ProjectModel.deleted_at.is_(None))
    result = await session.execute(select(ProjectModel).where(and_(*where)))
    project = result.scalar_one_or_none()
    if project is None:
        raise ProjectNotFoundError(str(project_id))
    return project


async def list_projects(
    session: AsyncSession,
    *,
    user: UserModel,
    filters: ListFilters,
    cursor: str | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
) -> tuple[Sequence[ProjectModel], str | None]:
    limit = max(1, min(limit, MAX_PAGE_SIZE))

    where: list[ColumnElement[bool]] = []
    if not filters.include_deleted:
        where.append(ProjectModel.deleted_at.is_(None))

    # Visibility:
    #   * CEO super-admins: every project.
    #   * Anyone with `project.create` in a business (= CEO + Assistant CEO
    #     by the default permission seed): every project in those businesses.
    #   * Everyone else: only projects they own OR are an active assignee on.
    if not user.is_super_admin:
        admin_business_ids = list(
            (
                await session.execute(
                    select(distinct(DepartmentMembershipModel.business_id))
                    .join(
                        DepartmentRoleModel,
                        DepartmentRoleModel.id == DepartmentMembershipModel.role_id,
                    )
                    .join(
                        DepartmentRolePermissionModel,
                        DepartmentRolePermissionModel.department_role_id
                        == DepartmentRoleModel.id,
                    )
                    .where(
                        DepartmentMembershipModel.user_id == user.id,
                        DepartmentRolePermissionModel.action_key == "project.create",
                        DepartmentRolePermissionModel.allowed.is_(True),
                    )
                )
            ).scalars().all()
        )
        assigned_subq = (
            select(ProjectStageAssignmentModel.project_id)
            .where(ProjectStageAssignmentModel.user_id == user.id)
            .where(ProjectStageAssignmentModel.removed_at.is_(None))
        )
        visibility_clauses: list[ColumnElement[bool]] = [
            ProjectModel.owner_id == user.id,
            ProjectModel.id.in_(assigned_subq),
        ]
        if admin_business_ids:
            visibility_clauses.append(
                ProjectModel.business_id.in_(admin_business_ids)
            )
        where.append(or_(*visibility_clauses))

    if filters.mine:
        where.append(ProjectModel.owner_id == user.id)
    if filters.owner_id is not None:
        where.append(ProjectModel.owner_id == filters.owner_id)
    if filters.stage_key is not None:
        where.append(ProjectModel.stage_key == filters.stage_key)

    query = select(ProjectModel).where(and_(*where)) if where else select(ProjectModel)
    query = query.order_by(ProjectModel.created_at.desc(), ProjectModel.id.desc())

    if cursor is not None:
        cursor_ts, cursor_id = _decode_cursor(cursor)
        # Composite cursor: order is (created_at DESC, id DESC), so "after the
        # cursor" means created_at < cursor_ts, or equal timestamp + id < cursor_id.
        query = query.where(
            or_(
                ProjectModel.created_at < cursor_ts,
                and_(
                    ProjectModel.created_at == cursor_ts,
                    ProjectModel.id < cursor_id,
                ),
            )
        )

    query = query.limit(limit + 1)
    result = await session.execute(query)
    rows = list(result.scalars().all())

    next_cursor: str | None = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = _encode_cursor(rows[-1])

    return rows, next_cursor


async def update_project(
    session: AsyncSession,
    *,
    actor: UserModel,
    project: ProjectModel,
    title: str | None = None,
    description: str | None = None,
    category: Category | None = None,
    due_date: object | None = None,
) -> ProjectModel:
    changed: dict[str, object] = {}
    if title is not None and title != project.title:
        project.title = title
        changed["title"] = title
    if description is not None and description != project.description:
        project.description = description
        changed["description"] = description
    if category is not None and category != project.category:
        project.category = category
        changed["category"] = category.value
    if due_date is not None and due_date != project.due_date:
        project.due_date = due_date  # type: ignore[assignment]
        changed["due_date"] = str(due_date)

    if changed:
        await activity_service.record(
            session,
            project_id=project.id,
            actor_id=actor.id,
            action="project.updated",
            metadata={"fields": list(changed.keys())},
        )
    return project


async def move_stage(
    session: AsyncSession,
    *,
    actor: UserModel,
    project: ProjectModel,
    target_stage_key: str,
) -> ProjectModel:
    """Move the project to `target_stage_key`. Permission check is the caller's
    job via `permission_service.can_user_move_to_stage` — this function just
    performs the write + activity log.

    Validates `target_stage_key` against the department's template registry
    and rejects unknown keys.
    """
    if project.stage_key == target_stage_key:
        return project

    department = project.department or await session.get(DepartmentModel, project.department_id)
    if department is None or not stage_registry.is_known_stage(
        department.template_key, target_stage_key
    ):
        raise StageNotFoundError(
            f"Stage {target_stage_key!r} not in template "
            f"{department.template_key if department else '<missing>'}"
        )

    previous_key = project.stage_key
    project.stage_key = target_stage_key

    await activity_service.record(
        session,
        project_id=project.id,
        actor_id=actor.id,
        action="project.stage_changed",
        metadata={"from": previous_key, "to": target_stage_key},
    )
    await assignment_service.seed_default(
        session, project=project, stage_key=target_stage_key, actor=actor
    )
    return project


async def auto_bump_stage(
    session: AsyncSession,
    *,
    project: ProjectModel,
    target_key: str,
    actor_id: uuid.UUID,
) -> None:
    """Best-effort "advance to this stage" called from feature services
    (script/edit/cast/shoot/location) when a domain event implies the
    project should auto-move forward.

    No-op if the target key isn't in this template, the project already
    sits on it, or the department can't be loaded. Permission checks are
    intentionally skipped — these calls happen inside trusted server-side
    flows triggered by other user actions that already passed their own
    permission gates.
    """
    department = project.department or await session.get(DepartmentModel, project.department_id)
    if department is None or not stage_registry.is_known_stage(department.template_key, target_key):
        return
    if project.stage_key == target_key:
        return
    previous_key = project.stage_key
    project.stage_key = target_key
    await activity_service.record(
        session,
        project_id=project.id,
        actor_id=actor_id,
        action="project.stage_changed",
        metadata={"from": previous_key, "to": target_key},
    )
    # Seed defaults for the new stage. We don't have a full UserModel here
    # (only an actor_id), so pass actor=None — `assigned_by` will be NULL,
    # which is the right semantic for "the system bumped you here".
    await assignment_service.seed_default(
        session, project=project, stage_key=target_key, actor=None
    )


async def soft_delete(
    session: AsyncSession, *, actor: UserModel, project: ProjectModel
) -> ProjectModel:
    if project.deleted_at is None:
        project.deleted_at = datetime.now(UTC)
        await activity_service.record(
            session,
            project_id=project.id,
            actor_id=actor.id,
            action="project.deleted",
        )
    return project


async def restore(
    session: AsyncSession, *, actor: UserModel, project: ProjectModel
) -> ProjectModel:
    if project.deleted_at is not None:
        project.deleted_at = None
        await activity_service.record(
            session,
            project_id=project.id,
            actor_id=actor.id,
            action="project.restored",
        )
    return project


__all__ = [
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "InvalidCursorError",
    "ListFilters",
    "ProjectNotFoundError",
    "StageNotFoundError",
    "auto_bump_stage",
    "create_project",
    "get_project",
    "list_projects",
    "move_stage",
    "restore",
    "soft_delete",
    "update_project",
]
