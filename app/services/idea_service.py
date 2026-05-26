"""Draft Idea domain service.

Owns the versioning + per-reviewer signoff loop for the `draft_idea`
stage. Permission checks live in routes; these functions assume the
caller has already authorised the action.

Lock semantics: an idea can be locked when every active assignee on
the project's `draft_idea` stage has a `looks_good` signoff on the
*latest* version. Locking stamps `ideas.locked_at/by` and advances the
project to `script_drafting`.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.idea_version import (
    IdeaModel,
    IdeaSignoffModel,
    IdeaVersionModel,
    SignoffDecision,
)
from app.models.project import ProjectModel
from app.models.project_stage_assignment import ProjectStageAssignmentModel
from app.models.user import UserModel
from app.services import activity_service, project_service

log = structlog.get_logger(__name__)


class IdeaNotFoundError(Exception):
    """No idea row for that project."""


class IdeaVersionNotFoundError(Exception):
    """No version row matches the given id."""


class IdeaAlreadyLockedError(Exception):
    """Cannot mutate the idea — it's locked."""


class IdeaLockGateError(Exception):
    """Lock denied — not every reviewer has signed off on the latest version."""

    def __init__(self, pending_reviewer_ids: list[uuid.UUID]) -> None:
        super().__init__(
            f"{len(pending_reviewer_ids)} reviewer(s) still need to approve "
            "the latest version"
        )
        self.pending_reviewer_ids = pending_reviewer_ids


# ---------- helpers ----------


async def _get_or_create_idea(
    session: AsyncSession, project: ProjectModel
) -> IdeaModel:
    result = await session.execute(
        select(IdeaModel).where(IdeaModel.project_id == project.id)
    )
    idea = result.scalar_one_or_none()
    if idea is not None:
        return idea
    idea = IdeaModel(business_id=project.business_id, project_id=project.id)
    session.add(idea)
    await session.flush()
    return idea


async def _next_version_number(session: AsyncSession, idea_id: uuid.UUID) -> int:
    result = await session.execute(
        select(func.coalesce(func.max(IdeaVersionModel.version_number), 0)).where(
            IdeaVersionModel.idea_id == idea_id
        )
    )
    return int(result.scalar_one()) + 1


async def get_idea(
    session: AsyncSession, *, project: ProjectModel
) -> IdeaModel | None:
    result = await session.execute(
        select(IdeaModel).where(IdeaModel.project_id == project.id)
    )
    return result.scalar_one_or_none()


async def get_version(
    session: AsyncSession, *, version_id: uuid.UUID
) -> IdeaVersionModel:
    row = await session.get(IdeaVersionModel, version_id)
    if row is None:
        raise IdeaVersionNotFoundError(str(version_id))
    return row


async def list_versions(
    session: AsyncSession, *, project: ProjectModel
) -> list[IdeaVersionModel]:
    result = await session.execute(
        select(IdeaVersionModel)
        .join(IdeaModel, IdeaModel.id == IdeaVersionModel.idea_id)
        .where(IdeaModel.project_id == project.id)
        .order_by(IdeaVersionModel.version_number.asc())
    )
    return list(result.scalars().all())


async def latest_version(
    session: AsyncSession, *, project: ProjectModel
) -> IdeaVersionModel | None:
    result = await session.execute(
        select(IdeaVersionModel)
        .join(IdeaModel, IdeaModel.id == IdeaVersionModel.idea_id)
        .where(IdeaModel.project_id == project.id)
        .order_by(IdeaVersionModel.version_number.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


# ---------- versions ----------


async def add_version(
    session: AsyncSession,
    *,
    project: ProjectModel,
    author: UserModel,
    body_markdown: str,
) -> IdeaVersionModel:
    idea = await _get_or_create_idea(session, project)
    if idea.locked_at is not None:
        raise IdeaAlreadyLockedError(
            "Cannot add a new version while the idea is locked"
        )
    version_number = await _next_version_number(session, idea.id)
    version = IdeaVersionModel(
        business_id=project.business_id,
        idea_id=idea.id,
        version_number=version_number,
        body_markdown=body_markdown,
        author_id=author.id,
        submitted_at=datetime.now(UTC),
    )
    session.add(version)
    await session.flush()
    idea.current_version_id = version.id

    await activity_service.record(
        session,
        project_id=project.id,
        actor_id=author.id,
        action="idea.version_created",
        metadata={"version_number": version_number},
    )
    return version


# ---------- signoffs ----------


async def list_signoffs(
    session: AsyncSession, *, version_id: uuid.UUID
) -> Sequence[IdeaSignoffModel]:
    result = await session.execute(
        select(IdeaSignoffModel)
        .where(IdeaSignoffModel.idea_version_id == version_id)
        .order_by(IdeaSignoffModel.created_at.asc())
    )
    return list(result.scalars().all())


async def add_signoff(
    session: AsyncSession,
    *,
    project: ProjectModel,
    version: IdeaVersionModel,
    reviewer: UserModel,
    decision: SignoffDecision,
    comment: str | None,
) -> IdeaSignoffModel:
    row = IdeaSignoffModel(
        business_id=project.business_id,
        idea_version_id=version.id,
        reviewer_id=reviewer.id,
        decision=decision,
        comment=comment,
    )
    session.add(row)
    await session.flush()

    await activity_service.record(
        session,
        project_id=project.id,
        actor_id=reviewer.id,
        action="idea.signoff",
        metadata={
            "version_number": version.version_number,
            "decision": decision.value,
        },
    )
    return row


# ---------- lock gate ----------


async def _latest_signoff_per_reviewer(
    session: AsyncSession, *, version_id: uuid.UUID
) -> dict[uuid.UUID, IdeaSignoffModel]:
    """For each reviewer who has signed off on this version, return their
    most recent signoff. Multiple signoffs from the same reviewer can
    accumulate (V2 revoke + re-approve); the latest wins."""
    rows = await session.execute(
        select(IdeaSignoffModel)
        .where(IdeaSignoffModel.idea_version_id == version_id)
        .order_by(
            IdeaSignoffModel.reviewer_id.asc(),
            IdeaSignoffModel.created_at.desc(),
        )
    )
    latest: dict[uuid.UUID, IdeaSignoffModel] = {}
    for row in rows.scalars():
        if row.reviewer_id in latest:
            continue
        latest[row.reviewer_id] = row
    return latest


async def _active_reviewer_ids(
    session: AsyncSession, *, project_id: uuid.UUID
) -> list[uuid.UUID]:
    result = await session.execute(
        select(ProjectStageAssignmentModel.user_id)
        .where(ProjectStageAssignmentModel.project_id == project_id)
        .where(ProjectStageAssignmentModel.stage_key == "draft_idea")
        .where(ProjectStageAssignmentModel.removed_at.is_(None))
    )
    return [row[0] for row in result.all()]


async def lock_gate_status(
    session: AsyncSession, *, project: ProjectModel
) -> tuple[bool, list[uuid.UUID]]:
    """Return `(can_lock, pending_reviewer_ids)`.

    `can_lock = True` iff every active draft_idea assignee has a
    `LOOKS_GOOD` signoff on the latest version. Empty version list →
    `(False, all_reviewers)`.
    """
    version = await latest_version(session, project=project)
    if version is None:
        return False, await _active_reviewer_ids(session, project_id=project.id)
    reviewers = await _active_reviewer_ids(session, project_id=project.id)
    if not reviewers:
        # No reviewers configured — anyone can lock. Edge case for misconfigured
        # departments; the route layer can still gate via permissions.
        return True, []
    latest = await _latest_signoff_per_reviewer(session, version_id=version.id)
    pending: list[uuid.UUID] = []
    for reviewer_id in reviewers:
        signoff = latest.get(reviewer_id)
        if signoff is None or signoff.decision != SignoffDecision.LOOKS_GOOD:
            pending.append(reviewer_id)
    return (len(pending) == 0), pending


async def lock_idea(
    session: AsyncSession, *, project: ProjectModel, actor: UserModel
) -> IdeaModel:
    idea = await get_idea(session, project=project)
    if idea is None:
        raise IdeaNotFoundError(
            "No idea drafted yet — create at least one version before locking"
        )
    if idea.locked_at is not None:
        # Idempotent — already locked, just return.
        return idea
    can_lock, pending = await lock_gate_status(session, project=project)
    if not can_lock:
        raise IdeaLockGateError(pending)

    idea.locked_at = datetime.now(UTC)
    idea.locked_by = actor.id

    # Advance the stage if we're still on draft_idea.
    if project.stage_key == "draft_idea":
        await project_service.auto_bump_stage(
            session,
            project=project,
            target_key="script_drafting",
            actor_id=actor.id,
        )
    await activity_service.record(
        session,
        project_id=project.id,
        actor_id=actor.id,
        action="idea.locked",
    )
    return idea


__all__ = [
    "IdeaAlreadyLockedError",
    "IdeaLockGateError",
    "IdeaNotFoundError",
    "IdeaVersionNotFoundError",
    "add_signoff",
    "add_version",
    "get_idea",
    "get_version",
    "latest_version",
    "list_signoffs",
    "list_versions",
    "lock_gate_status",
    "lock_idea",
]
