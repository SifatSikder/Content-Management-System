"""Location domain service.

Pure business logic. Adding the first confirmed location auto-advances a
project from LOCATION_SCOUTING to CASTING (spec §4 stage 5 → 6 trigger).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.location import LocationModel
from app.models.location_photo import LocationPhotoModel
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


class LocationNotFoundError(Exception):
    """Location does not exist."""


class LocationPhotoNotFoundError(Exception):
    """Photo does not exist."""


async def create_location(
    session: AsyncSession,
    *,
    project: ProjectModel,
    actor: UserModel,
    address: str,
    latitude: float | None,
    longitude: float | None,
    contact_name: str | None,
    contact_phone: str | None,
    scheduled_at: datetime | None,
) -> LocationModel:
    location = LocationModel(
        business_id=project.business_id,
        project_id=project.id,
        address=address,
        latitude=latitude,
        longitude=longitude,
        contact_name=contact_name,
        contact_phone=contact_phone,
        scheduled_at=scheduled_at,
    )
    session.add(location)
    await session.flush()
    await activity_service.record(
        session,
        project_id=project.id,
        actor_id=actor.id,
        action="location.created",
        metadata={"location_id": str(location.id), "address": address},
    )

    # Location scouting is the entry stage of the new content_creation flow,
    # so creating a location no longer needs to auto-advance — the project
    # is already there. Advancing to draft_idea is gated by the explicit
    # `Lock Location` action (added in Phase 3).

    return location


async def list_locations(
    session: AsyncSession, *, project_id: uuid.UUID
) -> Sequence[LocationModel]:
    result = await session.execute(
        select(LocationModel)
        .where(LocationModel.project_id == project_id)
        .order_by(LocationModel.created_at.desc())
    )
    return list(result.scalars().all())


async def get_location(session: AsyncSession, *, location_id: uuid.UUID) -> LocationModel:
    result = await session.execute(
        select(LocationModel).where(LocationModel.id == location_id)
    )
    location = result.scalar_one_or_none()
    if location is None:
        raise LocationNotFoundError(str(location_id))
    return location


async def update_location(
    session: AsyncSession,
    *,
    location: LocationModel,
    actor: UserModel,
    fields: dict[str, Any],
) -> LocationModel:
    """Apply a dict of changed fields. `confirmed` is handled separately."""
    changed: dict[str, Any] = {}
    for key, value in fields.items():
        if value is None:
            continue
        if getattr(location, key) != value:
            setattr(location, key, value)
            changed[key] = value if not isinstance(value, datetime) else value.isoformat()
    if changed:
        await activity_service.record(
            session,
            project_id=location.project_id,
            actor_id=actor.id,
            action="location.updated",
            metadata={"location_id": str(location.id), "fields": list(changed)},
        )
    return location


async def confirm_location(
    session: AsyncSession,
    *,
    location: LocationModel,
    project: ProjectModel,
    actor: UserModel,
    confirmed: bool,
) -> LocationModel:
    if location.confirmed == confirmed:
        return location
    location.confirmed = confirmed
    await activity_service.record(
        session,
        project_id=project.id,
        actor_id=actor.id,
        action="location.confirmed" if confirmed else "location.unconfirmed",
        metadata={"location_id": str(location.id)},
    )

    return location


class LocationLockError(Exception):
    """Raised when `lock_location` is called from an invalid stage."""


async def lock_location(
    session: AsyncSession, *, project: ProjectModel, actor: UserModel
) -> ProjectModel:
    """Explicit lock action — stamps `projects.location_locked_at/by` and
    advances the project from `location_scouting` to `draft_idea`.

    Idempotent: calling on a project already past `location_scouting` just
    re-stamps the columns (so the audit trail reflects who pressed the
    button most recently); calling on a project still on `location_scouting`
    additionally fires the stage advance.
    """
    if project.stage_key not in ("location_scouting", "draft_idea"):
        raise LocationLockError(
            f"Cannot lock location from stage {project.stage_key}"
        )
    project.location_locked_at = datetime.now(UTC)
    project.location_locked_by = actor.id
    if project.stage_key == "location_scouting":
        await _advance_stage(
            session, project=project, target_key="draft_idea", actor_id=actor.id
        )
    await activity_service.record(
        session,
        project_id=project.id,
        actor_id=actor.id,
        action="location.locked",
    )
    return project


async def unlock_location(
    session: AsyncSession, *, project: ProjectModel, actor: UserModel
) -> ProjectModel:
    """Clear the location lock so the Asst CEO can edit the location set
    again. Idempotent — calling on an already-unlocked project no-ops.
    Does NOT roll the stage back: if the project has already advanced
    past `location_scouting` the caller can move it back manually if
    they actually want to redo scouting from scratch.
    """
    if project.location_locked_at is None:
        return project
    project.location_locked_at = None
    project.location_locked_by = None
    await activity_service.record(
        session,
        project_id=project.id,
        actor_id=actor.id,
        action="location.unlocked",
    )
    return project


async def delete_location(
    session: AsyncSession, *, location: LocationModel, actor: UserModel
) -> None:
    project_id = location.project_id
    location_id = location.id
    await session.delete(location)
    await activity_service.record(
        session,
        project_id=project_id,
        actor_id=actor.id,
        action="location.deleted",
        metadata={"location_id": str(location_id)},
    )


# ---------- photos ----------

async def attach_photo(
    session: AsyncSession,
    *,
    location: LocationModel,
    uploader: UserModel,
    gcs_bucket: str,
    gcs_object_name: str,
    content_type: str,
    size_bytes: int,
) -> LocationPhotoModel:
    photo = LocationPhotoModel(
        business_id=location.business_id,
        location_id=location.id,
        uploader_id=uploader.id,
        gcs_bucket=gcs_bucket,
        gcs_object_name=gcs_object_name,
        content_type=content_type,
        size_bytes=size_bytes,
    )
    session.add(photo)
    await session.flush()
    await activity_service.record(
        session,
        project_id=location.project_id,
        actor_id=uploader.id,
        action="location.photo_added",
        metadata={"location_id": str(location.id), "photo_id": str(photo.id)},
    )
    return photo


async def get_photo(session: AsyncSession, *, photo_id: uuid.UUID) -> LocationPhotoModel:
    result = await session.execute(
        select(LocationPhotoModel).where(LocationPhotoModel.id == photo_id)
    )
    photo = result.scalar_one_or_none()
    if photo is None:
        raise LocationPhotoNotFoundError(str(photo_id))
    return photo


async def delete_photo(
    session: AsyncSession, *, photo: LocationPhotoModel, actor: UserModel
) -> None:
    location_id = photo.location_id
    photo_id = photo.id
    # Look up project_id for activity logging before delete.
    loc = await get_location(session, location_id=location_id)
    project_id = loc.project_id
    await session.delete(photo)
    await activity_service.record(
        session,
        project_id=project_id,
        actor_id=actor.id,
        action="location.photo_deleted",
        metadata={"location_id": str(location_id), "photo_id": str(photo_id)},
    )


__all__ = [
    "LocationLockError",
    "LocationNotFoundError",
    "LocationPhotoNotFoundError",
    "attach_photo",
    "confirm_location",
    "create_location",
    "delete_location",
    "delete_photo",
    "get_location",
    "get_photo",
    "list_locations",
    "lock_location",
    "unlock_location",
    "update_location",
]
