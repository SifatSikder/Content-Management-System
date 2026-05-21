"""Cast-member domain service.

When every cast member on a project is confirmed AND a location is confirmed,
the project auto-advances CASTING → SHOOT_SCHEDULED. This mirrors spec §4
row 7's "Location confirmed + cast confirmed" trigger.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cast_member import CastMemberModel
from app.models.enums import PipelineStage
from app.models.location import LocationModel
from app.models.project import ProjectModel
from app.models.user import UserModel
from app.services import activity_service


class CastMemberNotFoundError(Exception):
    """Cast member does not exist."""


async def create_cast_member(
    session: AsyncSession,
    *,
    project: ProjectModel,
    actor: UserModel,
    name: str,
    role_description: str | None,
    contact_email: str | None,
    contact_phone: str | None,
) -> CastMemberModel:
    cast = CastMemberModel(
        project_id=project.id,
        name=name,
        role_description=role_description,
        contact_email=contact_email,
        contact_phone=contact_phone,
    )
    session.add(cast)
    await session.flush()
    await activity_service.record(
        session,
        project_id=project.id,
        actor_id=actor.id,
        action="cast.created",
        metadata={"cast_id": str(cast.id), "name": name},
    )
    return cast


async def list_cast_members(
    session: AsyncSession, *, project_id: uuid.UUID
) -> Sequence[CastMemberModel]:
    result = await session.execute(
        select(CastMemberModel)
        .where(CastMemberModel.project_id == project_id)
        .order_by(CastMemberModel.created_at.desc())
    )
    return list(result.scalars().all())


async def get_cast_member(session: AsyncSession, *, cast_id: uuid.UUID) -> CastMemberModel:
    result = await session.execute(
        select(CastMemberModel).where(CastMemberModel.id == cast_id)
    )
    cast = result.scalar_one_or_none()
    if cast is None:
        raise CastMemberNotFoundError(str(cast_id))
    return cast


async def update_cast_member(
    session: AsyncSession,
    *,
    cast: CastMemberModel,
    actor: UserModel,
    fields: dict[str, Any],
) -> CastMemberModel:
    changed: list[str] = []
    for key, value in fields.items():
        if value is None:
            continue
        if getattr(cast, key) != value:
            setattr(cast, key, value)
            changed.append(key)
    if changed:
        await activity_service.record(
            session,
            project_id=cast.project_id,
            actor_id=actor.id,
            action="cast.updated",
            metadata={"cast_id": str(cast.id), "fields": changed},
        )
    return cast


async def attach_release_form(
    session: AsyncSession,
    *,
    cast: CastMemberModel,
    actor: UserModel,
    gcs_object_name: str,
) -> CastMemberModel:
    cast.release_form_object_name = gcs_object_name
    await activity_service.record(
        session,
        project_id=cast.project_id,
        actor_id=actor.id,
        action="cast.release_uploaded",
        metadata={"cast_id": str(cast.id)},
    )
    return cast


async def confirm_cast_member(
    session: AsyncSession,
    *,
    cast: CastMemberModel,
    project: ProjectModel,
    actor: UserModel,
    confirmed: bool,
) -> CastMemberModel:
    if cast.confirmed == confirmed:
        return cast
    cast.confirmed = confirmed
    await activity_service.record(
        session,
        project_id=project.id,
        actor_id=actor.id,
        action="cast.confirmed" if confirmed else "cast.unconfirmed",
        metadata={"cast_id": str(cast.id)},
    )

    # Stage auto-advance CASTING → SHOOT_SCHEDULED requires:
    #   1. at least one location confirmed
    #   2. at least one cast member, all confirmed
    if confirmed and project.stage == PipelineStage.CASTING:
        loc_q = await session.execute(
            select(LocationModel)
            .where(LocationModel.project_id == project.id)
            .where(LocationModel.confirmed.is_(True))
        )
        if loc_q.first() is not None:
            cast_q = await session.execute(
                select(CastMemberModel).where(CastMemberModel.project_id == project.id)
            )
            all_cast = list(cast_q.scalars().all())
            if all_cast and all(c.confirmed for c in all_cast):
                project.stage = PipelineStage.SHOOT_SCHEDULED
                await activity_service.record(
                    session,
                    project_id=project.id,
                    actor_id=actor.id,
                    action="project.stage_changed",
                    metadata={
                        "from": PipelineStage.CASTING.value,
                        "to": PipelineStage.SHOOT_SCHEDULED.value,
                    },
                )

    return cast


async def delete_cast_member(
    session: AsyncSession, *, cast: CastMemberModel, actor: UserModel
) -> None:
    project_id = cast.project_id
    cast_id = cast.id
    await session.delete(cast)
    await activity_service.record(
        session,
        project_id=project_id,
        actor_id=actor.id,
        action="cast.deleted",
        metadata={"cast_id": str(cast_id)},
    )


__all__ = [
    "CastMemberNotFoundError",
    "attach_release_form",
    "confirm_cast_member",
    "create_cast_member",
    "delete_cast_member",
    "get_cast_member",
    "list_cast_members",
    "update_cast_member",
]
