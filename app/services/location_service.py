"""Location domain service.

Pure business logic. Adding the first confirmed location auto-advances a
project from LOCATION_SCOUTING to CASTING (spec §4 stage 5 → 6 trigger).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
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
    target_id = await project_service.resolve_stage_id_by_key(
        session, department_id=project.department_id, key=target_key
    )
    if target_id is None or target_id == project.stage_id:
        return
    previous_key = project.stage.key
    project.stage_id = target_id
    await session.refresh(project, attribute_names=["stage"])
    await activity_service.record(
        session,
        project_id=project.id,
        actor_id=actor_id,
        action="project.stage_changed",
        metadata={"from": previous_key, "to": target_key},
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

    # First location on the project nudges the stage forward from idea/script
    # phases into "location_scouting". We don't auto-advance past scouting
    # until the location is confirmed (see `confirm_location`).
    if project.stage.key in ("script_locked", "script_review", "script_drafting", "idea"):
        await _advance_stage(
            session, project=project, target_key="location_scouting", actor_id=actor.id
        )

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

    # Spec §4 row 6: "Location confirmed" auto-advances location_scouting → casting.
    if confirmed and project.stage.key == "location_scouting":
        await _advance_stage(
            session, project=project, target_key="casting", actor_id=actor.id
        )
    return location


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
    "update_location",
]
