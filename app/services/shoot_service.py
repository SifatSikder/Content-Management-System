"""Shoot domain service.

State machine: SCHEDULED → IN_PROGRESS → WRAPPED. Forward-only — there's
no path back from WRAPPED. Wrapping a shoot auto-advances the project
SHOOT_SCHEDULED → SHOOT_DONE (spec §4 row 9).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PipelineStage, ShootStatus
from app.models.project import ProjectModel
from app.models.shoot import ShootModel
from app.models.user import UserModel
from app.services import activity_service


class ShootNotFoundError(Exception):
    """Shoot does not exist."""


class IllegalShootTransitionError(Exception):
    """Invalid state transition for a shoot (e.g. WRAPPED → SCHEDULED)."""


_VALID_TRANSITIONS: dict[ShootStatus, frozenset[ShootStatus]] = {
    ShootStatus.SCHEDULED: frozenset({ShootStatus.IN_PROGRESS}),
    ShootStatus.IN_PROGRESS: frozenset({ShootStatus.WRAPPED}),
    ShootStatus.WRAPPED: frozenset(),
}


async def create_shoot(
    session: AsyncSession,
    *,
    project: ProjectModel,
    actor: UserModel,
    scheduled_at: datetime | None,
    gear_checklist: dict[str, Any],
) -> ShootModel:
    shoot = ShootModel(
        project_id=project.id,
        scheduled_at=scheduled_at,
        gear_checklist_json=gear_checklist,
    )
    session.add(shoot)
    await session.flush()
    await activity_service.record(
        session,
        project_id=project.id,
        actor_id=actor.id,
        action="shoot.created",
        metadata={
            "shoot_id": str(shoot.id),
            "scheduled_at": scheduled_at.isoformat() if scheduled_at else None,
        },
    )
    return shoot


async def list_shoots(
    session: AsyncSession, *, project_id: uuid.UUID
) -> Sequence[ShootModel]:
    result = await session.execute(
        select(ShootModel)
        .where(ShootModel.project_id == project_id)
        .order_by(ShootModel.scheduled_at.asc().nulls_last(), ShootModel.created_at.desc())
    )
    return list(result.scalars().all())


async def get_shoot(session: AsyncSession, *, shoot_id: uuid.UUID) -> ShootModel:
    result = await session.execute(select(ShootModel).where(ShootModel.id == shoot_id))
    shoot = result.scalar_one_or_none()
    if shoot is None:
        raise ShootNotFoundError(str(shoot_id))
    return shoot


async def update_shoot(
    session: AsyncSession,
    *,
    shoot: ShootModel,
    actor: UserModel,
    scheduled_at: datetime | None = None,
    gear_checklist: dict[str, Any] | None = None,
) -> ShootModel:
    changed: list[str] = []
    if scheduled_at is not None and shoot.scheduled_at != scheduled_at:
        shoot.scheduled_at = scheduled_at
        changed.append("scheduled_at")
    if gear_checklist is not None and shoot.gear_checklist_json != gear_checklist:
        shoot.gear_checklist_json = gear_checklist
        changed.append("gear_checklist")
    if changed:
        await activity_service.record(
            session,
            project_id=shoot.project_id,
            actor_id=actor.id,
            action="shoot.updated",
            metadata={"shoot_id": str(shoot.id), "fields": changed},
        )
    return shoot


async def attach_call_sheet(
    session: AsyncSession,
    *,
    shoot: ShootModel,
    actor: UserModel,
    gcs_object_name: str,
) -> ShootModel:
    shoot.call_sheet_object_name = gcs_object_name
    await activity_service.record(
        session,
        project_id=shoot.project_id,
        actor_id=actor.id,
        action="shoot.call_sheet_uploaded",
        metadata={"shoot_id": str(shoot.id)},
    )
    return shoot


async def transition_shoot(
    session: AsyncSession,
    *,
    shoot: ShootModel,
    project: ProjectModel,
    actor: UserModel,
    target: ShootStatus,
) -> ShootModel:
    if target not in _VALID_TRANSITIONS.get(shoot.status, frozenset()):
        raise IllegalShootTransitionError(
            f"Cannot transition shoot from {shoot.status.value} to {target.value}"
        )
    previous = shoot.status
    shoot.status = target
    now = datetime.now(UTC)
    if target == ShootStatus.IN_PROGRESS:
        shoot.started_at = now
    elif target == ShootStatus.WRAPPED:
        shoot.wrapped_at = now

    await activity_service.record(
        session,
        project_id=project.id,
        actor_id=actor.id,
        action="shoot.transitioned",
        metadata={
            "shoot_id": str(shoot.id),
            "from": previous.value,
            "to": target.value,
        },
    )

    # Spec §4 row 9: wrap shoot → SHOOT_DONE.
    if target == ShootStatus.WRAPPED and project.stage == PipelineStage.SHOOT_SCHEDULED:
        project.stage = PipelineStage.SHOOT_DONE
        await activity_service.record(
            session,
            project_id=project.id,
            actor_id=actor.id,
            action="project.stage_changed",
            metadata={
                "from": PipelineStage.SHOOT_SCHEDULED.value,
                "to": PipelineStage.SHOOT_DONE.value,
            },
        )

    return shoot


async def delete_shoot(
    session: AsyncSession, *, shoot: ShootModel, actor: UserModel
) -> None:
    project_id = shoot.project_id
    shoot_id = shoot.id
    await session.delete(shoot)
    await activity_service.record(
        session,
        project_id=project_id,
        actor_id=actor.id,
        action="shoot.deleted",
        metadata={"shoot_id": str(shoot_id)},
    )


__all__ = [
    "IllegalShootTransitionError",
    "ShootNotFoundError",
    "attach_call_sheet",
    "create_shoot",
    "delete_shoot",
    "get_shoot",
    "list_shoots",
    "transition_shoot",
    "update_shoot",
]
