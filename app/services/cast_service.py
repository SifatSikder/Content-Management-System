"""Cast-member domain service.

`confirm_cast_member` only flips the boolean — stage advance is now
explicit via `lock_casting` (the "Lock Casting" button) instead of the
old "all confirmed" heuristic.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cast_member import CastMemberModel
from app.models.project import ProjectModel
from app.models.user import UserModel
from app.services import activity_service, project_service


async def _advance_stage(
    session: AsyncSession,
    *,
    project: ProjectModel,
    target_key: str,
    actor_id: uuid.UUID,
) -> None:
    await project_service.auto_bump_stage(
        session, project=project, target_key=target_key, actor_id=actor_id
    )


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
    kind: str = "cast",
    source: str | None = None,
    notes: str | None = None,
) -> CastMemberModel:
    cast = CastMemberModel(
        project_id=project.id,
        name=name,
        role_description=role_description,
        contact_email=contact_email,
        contact_phone=contact_phone,
        kind=kind,
        source=source,
        notes=notes,
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

    return cast


class CastingLockError(Exception):
    """Raised when `lock_casting` is called from an invalid stage."""


async def lock_casting(
    session: AsyncSession, *, project: ProjectModel, actor: UserModel
) -> ProjectModel:
    """Explicit "Lock Casting" — stamps `projects.casting_locked_at/by` and
    advances `casting → shoot_schedule`. Idempotent: re-stamps the columns
    if pressed again after the stage already advanced."""
    if project.stage_key not in ("casting", "shoot_schedule"):
        raise CastingLockError(
            f"Cannot lock casting from stage {project.stage_key}"
        )
    project.casting_locked_at = datetime.now(UTC)
    project.casting_locked_by = actor.id
    if project.stage_key == "casting":
        await _advance_stage(
            session, project=project, target_key="shoot_schedule", actor_id=actor.id
        )
    await activity_service.record(
        session,
        project_id=project.id,
        actor_id=actor.id,
        action="casting.locked",
    )
    return project


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
    "CastingLockError",
    "attach_release_form",
    "confirm_cast_member",
    "create_cast_member",
    "delete_cast_member",
    "get_cast_member",
    "list_cast_members",
    "lock_casting",
    "update_cast_member",
]
