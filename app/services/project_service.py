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

from app.models.enums import Category, PipelineStage, Role
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


@dataclass(frozen=True)
class ListFilters:
    stage: PipelineStage | None = None
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


async def create_project(
    session: AsyncSession,
    *,
    actor: UserModel,
    title: str,
    category: Category,
    description: str | None = None,
    due_date: object | None = None,
    owner_id_override: uuid.UUID | None = None,
) -> ProjectModel:
    """Create a project. Activity row + commit are the caller's responsibility."""
    owner = actor
    if owner_id_override is not None and actor.role in (Role.CEO, Role.ASSISTANT_DIRECTOR):
        override = await session.get(UserModel, owner_id_override)
        if override is None:
            raise ProjectNotFoundError(f"owner_id_override {owner_id_override} not found")
        owner = override

    project = ProjectModel(
        title=title,
        description=description,
        category=category,
        stage=PipelineStage.IDEA,
        owner=owner,
        due_date=due_date,
    )
    session.add(project)
    await session.flush()

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
    if filters.stage is not None:
        where.append(ProjectModel.stage == filters.stage)

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
    target_stage: PipelineStage,
) -> ProjectModel:
    """Move the project to `target_stage`. Permission check is the caller's job
    via `can_user_move_to_stage` — this function just performs the write.
    """
    if project.stage == target_stage:
        return project
    previous = project.stage
    project.stage = target_stage

    await activity_service.record(
        session,
        project_id=project.id,
        actor_id=actor.id,
        action="project.stage_changed",
        metadata={"from": previous.value, "to": target_stage.value},
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
    "create_project",
    "get_project",
    "list_projects",
    "move_stage",
    "restore",
    "soft_delete",
    "update_project",
]
