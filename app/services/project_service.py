"""Project domain service.

Pure business logic — no FastAPI imports. Each mutating method logs an
activity entry; the caller owns the transaction.

Cursor pagination: cursors are opaque base64 strings encoding
`<created_at_iso>|<uuid>`. The list query orders by `(created_at DESC, id DESC)`
and uses the cursor as a `(created_at, id) <` filter for stability across
inserts.
"""

from __future__ import annotations

import base64
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

import structlog
from sqlalchemy import ColumnElement, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.department_stage import DepartmentStageModel
from app.models.enums import Category, Role
from app.models.project import ProjectModel
from app.models.user import UserModel
from app.services import activity_service

log = structlog.get_logger(__name__)

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100


class ProjectNotFoundError(Exception):
    """Project does not exist (or is soft-deleted when not requested)."""


class InvalidCursorError(Exception):
    """Pagination cursor failed to decode."""


class StageNotFoundError(Exception):
    """No stage with the given key exists in the requested department."""


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


async def _first_stage_id_for_department(
    session: AsyncSession, *, department_id: uuid.UUID
) -> uuid.UUID:
    """Return the lowest-order_index stage in a department.

    Used as the initial stage for newly-created projects. Raises if the
    department has no stages — that's a misconfiguration (every template
    must define at least one).
    """
    result = await session.execute(
        select(DepartmentStageModel.id)
        .where(DepartmentStageModel.department_id == department_id)
        .order_by(DepartmentStageModel.order_index.asc(), DepartmentStageModel.created_at.asc())
        .limit(1)
    )
    stage_id = result.scalar_one_or_none()
    if stage_id is None:
        raise StageNotFoundError(
            f"Department {department_id} has no stages — cannot create a project"
        )
    return stage_id


async def resolve_stage_id_by_key(
    session: AsyncSession,
    *,
    department_id: uuid.UUID,
    key: str,
) -> uuid.UUID | None:
    """Return the stage id whose key matches inside the given department."""
    result = await session.execute(
        select(DepartmentStageModel.id).where(
            DepartmentStageModel.department_id == department_id,
            DepartmentStageModel.key == key,
        )
    )
    return result.scalar_one_or_none()


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
    stage_id: uuid.UUID | None = None,
) -> ProjectModel:
    """Create a project. Activity row + commit are the caller's responsibility.

    `stage_id` defaults to the department's first stage (lowest order_index)
    so the caller doesn't have to know about the per-template entry stage.
    """
    owner = actor
    if owner_id_override is not None and actor.role in (Role.CEO, Role.ASSISTANT_DIRECTOR):
        override = await session.get(UserModel, owner_id_override)
        if override is None:
            raise ProjectNotFoundError(f"owner_id_override {owner_id_override} not found")
        owner = override

    if stage_id is None:
        stage_id = await _first_stage_id_for_department(
            session, department_id=department_id
        )

    project = ProjectModel(
        title=title,
        description=description,
        category=category,
        business_id=business_id,
        department_id=department_id,
        stage_id=stage_id,
        owner=owner,
        due_date=due_date,
    )
    session.add(project)
    await session.flush()
    # Eager-load the relationships so callers can read `project.stage.key`
    # immediately after creation without an extra refresh.
    await session.refresh(project, attribute_names=["stage", "department"])

    await activity_service.record(
        session,
        project_id=project.id,
        actor_id=actor.id,
        action="project.created",
        metadata={"title": title, "category": category.value},
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

    # Visibility: crew sees only assigned (proxied by ownership); others see all.
    if user.role == Role.CREW:
        where.append(ProjectModel.owner_id == user.id)

    if filters.mine:
        where.append(ProjectModel.owner_id == user.id)
    if filters.owner_id is not None:
        where.append(ProjectModel.owner_id == filters.owner_id)
    if filters.stage_key is not None:
        # Join through department_stages to filter by stage key. The
        # business-context RLS policy already scopes stages to the current
        # business so the comparison is unambiguous within one tenant.
        where.append(
            ProjectModel.stage_id.in_(
                select(DepartmentStageModel.id).where(
                    DepartmentStageModel.key == filters.stage_key
                )
            )
        )

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
    target_stage_id: uuid.UUID,
) -> ProjectModel:
    """Move the project to `target_stage_id`. Permission check is the caller's
    job via `permission_service.can_user_move_to_stage` — this function just
    performs the write + activity log.
    """
    if project.stage_id == target_stage_id:
        return project
    previous_key = project.stage.key if project.stage else None
    target_q = await session.execute(
        select(DepartmentStageModel).where(DepartmentStageModel.id == target_stage_id)
    )
    target = target_q.scalar_one_or_none()
    if target is None:
        raise StageNotFoundError(str(target_stage_id))

    project.stage_id = target_stage_id
    project.stage = target  # keep the relationship in sync for downstream reads

    await activity_service.record(
        session,
        project_id=project.id,
        actor_id=actor.id,
        action="project.stage_changed",
        metadata={"from": previous_key, "to": target.key},
    )
    return project


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
    "create_project",
    "get_project",
    "list_projects",
    "move_stage",
    "resolve_stage_id_by_key",
    "restore",
    "soft_delete",
    "update_project",
]
