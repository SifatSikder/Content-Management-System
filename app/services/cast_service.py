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

import structlog

from app.models.cast_member import CastMemberModel
from app.models.project import ProjectModel
from app.models.project_stage_assignment import ProjectStageAssignmentModel
from app.models.user import UserModel
from app.services import activity_service, email_service, project_service

log = structlog.get_logger(__name__)


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
        business_id=project.business_id,
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


class CastingLockError(Exception):
    """Raised when `lock_casting` is called from an invalid stage."""


async def lock_casting(
    session: AsyncSession, *, project: ProjectModel, actor: UserModel
) -> ProjectModel:
    """Explicit "Lock Casting" — stamps `projects.casting_locked_at/by`
    and advances `casting → shooting`. The stage's default handoff
    (see `_handoffs.py`) auto-assigns the department's director(s);
    this function then emails them so they know the shoot is theirs.
    Idempotent on the stamp columns if pressed again after the stage
    already advanced."""
    if project.stage_key not in ("casting", "shooting"):
        raise CastingLockError(
            f"Cannot lock casting from stage {project.stage_key}"
        )
    just_advanced = project.stage_key == "casting"
    project.casting_locked_at = datetime.now(UTC)
    project.casting_locked_by = actor.id
    if just_advanced:
        await _advance_stage(
            session, project=project, target_key="shooting", actor_id=actor.id
        )
    await activity_service.record(
        session,
        project_id=project.id,
        actor_id=actor.id,
        action="casting.locked",
    )
    # Email the freshly-assigned director(s). Only do this on the first
    # lock (when the stage actually advanced); a re-lock from `shooting`
    # would re-notify people unnecessarily.
    if just_advanced:
        await _notify_shooting_assignees(session, project=project, actor=actor)
    return project


async def _notify_shooting_assignees(
    session: AsyncSession, *, project: ProjectModel, actor: UserModel
) -> None:
    """Email every active non-owner assignee on the `shooting` stage so
    the director(s) know the shoot is kicked off. Failures are
    swallowed — the data write is the source of truth."""
    result = await session.execute(
        select(UserModel.email, UserModel.name)
        .join(
            ProjectStageAssignmentModel,
            ProjectStageAssignmentModel.user_id == UserModel.id,
        )
        .where(ProjectStageAssignmentModel.project_id == project.id)
        .where(ProjectStageAssignmentModel.stage_key == "shooting")
        .where(ProjectStageAssignmentModel.removed_at.is_(None))
        .where(ProjectStageAssignmentModel.user_id != project.owner_id)
    )
    recipients = list(result.all())
    if not recipients:
        return

    project_url = f"/projects/{project.id}"
    subject = f"Shooting kicked off: {project.title}"
    html = (
        f"<p>{actor.name} locked casting on <strong>{project.title}</strong>. "
        f"The shoot is yours — schedule it, run it, and upload the raw cuts "
        f"on the Shoot tab when wrapped.</p>"
        f"<p><a href=\"{project_url}\">Open the project</a></p>"
    )
    for email, _name in recipients:
        try:
            await email_service.send_html_email(
                to=email, subject=subject, html=html
            )
        except email_service.EmailNotConfiguredError:
            log.info(
                "shooting_kickoff_email_skipped_not_configured",
                to=email,
                project_id=str(project.id),
            )
        except Exception as exc:
            log.warning(
                "shooting_kickoff_email_failed",
                to=email,
                project_id=str(project.id),
                error=str(exc),
            )


async def unlock_casting(
    session: AsyncSession, *, project: ProjectModel, actor: UserModel
) -> ProjectModel:
    """Clear the casting lock so the owner can edit the cast set again.
    Symmetric to `lock_casting`: if the project is currently on
    `shooting` (just locked), roll it back to `casting`. If work
    has progressed further (Shoot, Edit, …) leave the stage alone — the
    owner can drag it back manually. Mirrors `unlock_script`."""
    if project.casting_locked_at is None:
        return project
    project.casting_locked_at = None
    project.casting_locked_by = None
    if project.stage_key == "shooting":
        await _advance_stage(
            session, project=project, target_key="casting", actor_id=actor.id
        )
    await activity_service.record(
        session,
        project_id=project.id,
        actor_id=actor.id,
        action="casting.unlocked",
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
    "create_cast_member",
    "delete_cast_member",
    "get_cast_member",
    "list_cast_members",
    "lock_casting",
    "unlock_casting",
    "update_cast_member",
]
