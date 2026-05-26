"""Per-stage project assignment service.

Pure service (no FastAPI imports). Callers commit the session.

Active assignment = `removed_at IS NULL`. Adding the same user twice to the
same (project, stage) is a no-op — `add()` returns the existing active row.
Removing sets `removed_at` rather than deleting, so history is preserved.

Default-assignment on stage transitions lives here as `seed_default(...)`,
called from `project_service` when a project enters a new stage. Phase 2's
default is "the project owner". Phase 4 replaces this with slot-derived
defaults via `slot_service`.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.project import ProjectModel
from app.models.project_stage_assignment import ProjectStageAssignmentModel
from app.models.user import UserModel
from app.services import handoff_service

log = structlog.get_logger(__name__)


class AssignmentNotFoundError(Exception):
    """Assignment row does not exist or is already removed."""


async def list_active(
    session: AsyncSession, *, project_id: uuid.UUID, stage_key: str
) -> Sequence[ProjectStageAssignmentModel]:
    result = await session.execute(
        select(ProjectStageAssignmentModel)
        .where(ProjectStageAssignmentModel.project_id == project_id)
        .where(ProjectStageAssignmentModel.stage_key == stage_key)
        .where(ProjectStageAssignmentModel.removed_at.is_(None))
        .options(selectinload(ProjectStageAssignmentModel.user))
        .order_by(ProjectStageAssignmentModel.assigned_at.asc())
    )
    return list(result.scalars().all())


async def list_active_for_project(
    session: AsyncSession, *, project_id: uuid.UUID
) -> Sequence[ProjectStageAssignmentModel]:
    """All currently-active assignments for a project across every stage.
    Used by the kanban card list endpoint so each card knows its current
    assignees without an extra round-trip per card."""
    result = await session.execute(
        select(ProjectStageAssignmentModel)
        .where(ProjectStageAssignmentModel.project_id == project_id)
        .where(ProjectStageAssignmentModel.removed_at.is_(None))
        .options(selectinload(ProjectStageAssignmentModel.user))
        .order_by(ProjectStageAssignmentModel.assigned_at.asc())
    )
    return list(result.scalars().all())


async def _get_active(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    stage_key: str,
    user_id: uuid.UUID,
) -> ProjectStageAssignmentModel | None:
    result = await session.execute(
        select(ProjectStageAssignmentModel)
        .where(ProjectStageAssignmentModel.project_id == project_id)
        .where(ProjectStageAssignmentModel.stage_key == stage_key)
        .where(ProjectStageAssignmentModel.user_id == user_id)
        .where(ProjectStageAssignmentModel.removed_at.is_(None))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def add(
    session: AsyncSession,
    *,
    project: ProjectModel,
    stage_key: str,
    user_id: uuid.UUID,
    actor: UserModel | None,
) -> ProjectStageAssignmentModel:
    existing = await _get_active(
        session, project_id=project.id, stage_key=stage_key, user_id=user_id
    )
    if existing is not None:
        return existing
    row = ProjectStageAssignmentModel(
        business_id=project.business_id,
        project_id=project.id,
        stage_key=stage_key,
        user_id=user_id,
        assigned_at=datetime.now(UTC),
        assigned_by=actor.id if actor is not None else None,
    )
    session.add(row)
    await session.flush()
    return row


async def remove(
    session: AsyncSession,
    *,
    project: ProjectModel,
    stage_key: str,
    user_id: uuid.UUID,
) -> ProjectStageAssignmentModel:
    existing = await _get_active(
        session, project_id=project.id, stage_key=stage_key, user_id=user_id
    )
    if existing is None:
        raise AssignmentNotFoundError(
            f"No active assignment for user {user_id} on project {project.id} "
            f"stage {stage_key!r}"
        )
    existing.removed_at = datetime.now(UTC)
    await session.flush()
    return existing


async def seed_default(
    session: AsyncSession,
    *,
    project: ProjectModel,
    stage_key: str,
    actor: UserModel | None,
) -> None:
    """Seed default assignees when a project enters `stage_key`.

    Looks up the department's `stage_handoff` rule and auto-assigns
    every user holding one of the configured roles. Falls back to the
    project owner if no handoff is configured OR every role resolves
    to zero users (so cards are never born unassigned).
    """
    user_ids = await handoff_service.default_assignees_for_stage(
        session, department_id=project.department_id, stage_key=stage_key
    )
    if not user_ids:
        await add(
            session,
            project=project,
            stage_key=stage_key,
            user_id=project.owner_id,
            actor=actor,
        )
        return
    for user_id in user_ids:
        await add(
            session,
            project=project,
            stage_key=stage_key,
            user_id=user_id,
            actor=actor,
        )


__all__ = [
    "AssignmentNotFoundError",
    "add",
    "list_active",
    "list_active_for_project",
    "remove",
    "seed_default",
]
