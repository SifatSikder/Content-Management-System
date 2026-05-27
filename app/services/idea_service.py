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

from app.models.department_membership import DepartmentMembershipModel
from app.models.department_role import DepartmentRoleModel
from app.models.idea_version import (
    IdeaModel,
    IdeaSignoffModel,
    IdeaVersionModel,
    SignoffDecision,
)
from app.models.project import ProjectModel
from app.models.project_stage_assignment import ProjectStageAssignmentModel
from app.models.user import UserModel
from app.services import (
    activity_service,
    assignment_service,
    email_service,
    project_service,
)

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


async def reviewer_count(
    session: AsyncSession, *, project: ProjectModel
) -> int:
    """Count of non-owner active assignees on draft_idea — i.e. how
    many reviewers the owner has pulled in via Request feedback. Used
    by the UI to decide whether the owner can still edit the current
    version in place or has to save a new V."""
    ids = await _active_reviewer_ids(session, project=project)
    return len(ids)


class IdeaVersionNotEditableError(Exception):
    """Cannot edit the version body in place — either the idea is
    locked or reviewers have already been pulled in."""


async def update_version_body(
    session: AsyncSession,
    *,
    project: ProjectModel,
    version: IdeaVersionModel,
    actor: UserModel,
    body_markdown: str,
) -> IdeaVersionModel:
    """Edit the body of an existing idea version in place. Only allowed
    while the idea is unlocked AND no reviewers have been pulled in
    yet (i.e. before the owner has pressed Request feedback). After
    that, edits start a new version via `add_version`.

    Also enforces: the version must be the LATEST one — we don't allow
    editing back into older immutable revisions.
    """
    idea = await get_idea(session, project=project)
    if idea is None or idea.locked_at is not None:
        raise IdeaVersionNotEditableError("Idea is locked")
    latest = await latest_version(session, project=project)
    if latest is None or latest.id != version.id:
        raise IdeaVersionNotEditableError(
            "Only the latest version can be edited in place"
        )
    if await reviewer_count(session, project=project) > 0:
        raise IdeaVersionNotEditableError(
            "Reviewers already pulled in — save a new version instead"
        )
    version.body_markdown = body_markdown
    await session.flush()
    await activity_service.record(
        session,
        project_id=project.id,
        actor_id=actor.id,
        action="idea.version_edited",
        metadata={"version_number": version.version_number},
    )
    return version


async def _active_reviewer_ids(
    session: AsyncSession, *, project: ProjectModel
) -> list[uuid.UUID]:
    """Active draft_idea assignees EXCLUDING the project owner — the
    owner is the author of the idea and doesn't sign off on her own
    draft. Only the reviewers she pulled in via Request feedback count
    toward the lock gate."""
    result = await session.execute(
        select(ProjectStageAssignmentModel.user_id)
        .where(ProjectStageAssignmentModel.project_id == project.id)
        .where(ProjectStageAssignmentModel.stage_key == "draft_idea")
        .where(ProjectStageAssignmentModel.removed_at.is_(None))
        .where(ProjectStageAssignmentModel.user_id != project.owner_id)
    )
    return [row[0] for row in result.all()]


async def lock_gate_status(
    session: AsyncSession, *, project: ProjectModel
) -> tuple[bool, list[uuid.UUID]]:
    """Return `(can_lock, pending_reviewer_ids)`.

    `can_lock = True` iff every active draft_idea reviewer (everyone
    other than the owner) has a `LOOKS_GOOD` signoff on the latest
    version. Empty version list → `(False, all_reviewers)`.
    """
    version = await latest_version(session, project=project)
    if version is None:
        return False, await _active_reviewer_ids(session, project=project)
    reviewers = await _active_reviewer_ids(session, project=project)
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


async def unlock_idea(
    session: AsyncSession, *, project: ProjectModel, actor: UserModel
) -> IdeaModel | None:
    """Clear the idea lock so the owner can keep editing / save a new
    version. Idempotent — calling on an already-unlocked idea no-ops.
    Does NOT roll the stage back: if the project has already moved past
    `draft_idea` the caller can drag it back manually if they want to
    redo the idea from scratch (mirrors `unlock_location`)."""
    idea = await get_idea(session, project=project)
    if idea is None or idea.locked_at is None:
        return idea
    idea.locked_at = None
    idea.locked_by = None
    await activity_service.record(
        session,
        project_id=project.id,
        actor_id=actor.id,
        action="idea.unlocked",
    )
    return idea


# Role keys whose holders get pulled in for idea-enhancement feedback.
# Mirrors the spec — Asst CEO drafts, CEO + Director give feedback.
_ENHANCEMENT_REVIEWER_ROLE_KEYS = ("ceo", "director", "junior_director")


class NoEnhancementReviewersError(Exception):
    """No CEO / Director members in the department to assign."""


async def list_enhancement_candidates(
    session: AsyncSession, *, project: ProjectModel
) -> list[tuple[uuid.UUID, str, str, str]]:
    """Return `(user_id, email, name, role_key)` for every dept member
    holding a CEO / Director role — the universe the owner can pick
    from when requesting idea-enhancement feedback."""
    rows = await session.execute(
        select(
            DepartmentMembershipModel.user_id,
            UserModel.email,
            UserModel.name,
            DepartmentRoleModel.key,
        )
        .join(
            DepartmentRoleModel,
            DepartmentRoleModel.id == DepartmentMembershipModel.role_id,
        )
        .join(UserModel, UserModel.id == DepartmentMembershipModel.user_id)
        .where(DepartmentMembershipModel.department_id == project.department_id)
        .where(DepartmentRoleModel.key.in_(_ENHANCEMENT_REVIEWER_ROLE_KEYS))
        .order_by(UserModel.name.asc())
    )
    return [(r.user_id, r.email, r.name, r.key) for r in rows.all()]


async def request_enhancement(
    session: AsyncSession,
    *,
    project: ProjectModel,
    actor: UserModel,
    reviewer_user_ids: list[uuid.UUID],
) -> list[uuid.UUID]:
    """Assign the chosen reviewers (must each hold CEO or Director role
    in the project's dept) to the `draft_idea` stage and email each one.

    Returns the list of newly-assigned user ids. Idempotent: re-running
    with the same reviewers doesn't add duplicate rows
    (assignment_service.add is upsert-shaped). Email failures are
    swallowed — logged but don't roll back the assignments.
    """
    if await latest_version(session, project=project) is None:
        raise IdeaNotFoundError(
            "Save at least one draft version before requesting enhancement"
        )
    if not reviewer_user_ids:
        raise NoEnhancementReviewersError(
            "Pick at least one reviewer before requesting feedback"
        )

    candidates = await list_enhancement_candidates(session, project=project)
    by_id = {row[0]: row for row in candidates}
    invalid = [str(uid) for uid in reviewer_user_ids if uid not in by_id]
    if invalid:
        raise NoEnhancementReviewersError(
            f"Not eligible reviewers (must hold CEO or Director role): {invalid}"
        )
    reviewers = [
        (uid, by_id[uid][1], by_id[uid][2]) for uid in reviewer_user_ids
    ]

    newly_assigned: list[uuid.UUID] = []
    for user_id, _email, _name in reviewers:
        row = await assignment_service.add(
            session,
            project=project,
            stage_key="draft_idea",
            user_id=user_id,
            actor=actor,
        )
        # `add` is upsert-shaped; existing active rows are returned as-is.
        # Treat anyone whose row was created in this call as newly assigned.
        if row.assigned_by == actor.id and row.removed_at is None:
            newly_assigned.append(user_id)

    await activity_service.record(
        session,
        project_id=project.id,
        actor_id=actor.id,
        action="idea.enhancement_requested",
        metadata={"reviewer_count": len(reviewers)},
    )

    # Fire-and-forget email notifications. Don't let mail failures roll
    # back the assignment write — the data is the source of truth.
    project_url = f"/projects/{project.id}"
    subject = f"Feedback requested: {project.title}"
    html = (
        f"<p>{actor.name} asked for your feedback on the draft idea for "
        f"<strong>{project.title}</strong>.</p>"
        f"<p>Open the project, switch to the <em>Idea</em> tab, and either "
        f"approve or request changes.</p>"
        f"<p><a href=\"{project_url}\">Go to project</a></p>"
    )
    for _user_id, email, _name in reviewers:
        try:
            await email_service.send_html_email(
                to=email, subject=subject, html=html
            )
        except email_service.EmailNotConfiguredError:
            log.info(
                "idea_enhancement_email_skipped_not_configured",
                to=email,
                project_id=str(project.id),
            )
        except Exception as exc:
            log.warning(
                "idea_enhancement_email_failed",
                to=email,
                project_id=str(project.id),
                error=str(exc),
            )

    return newly_assigned


__all__ = [
    "IdeaAlreadyLockedError",
    "IdeaLockGateError",
    "IdeaNotFoundError",
    "IdeaVersionNotEditableError",
    "IdeaVersionNotFoundError",
    "NoEnhancementReviewersError",
    "add_signoff",
    "add_version",
    "get_idea",
    "get_version",
    "latest_version",
    "list_signoffs",
    "list_versions",
    "list_enhancement_candidates",
    "lock_gate_status",
    "lock_idea",
    "request_enhancement",
    "reviewer_count",
    "unlock_idea",
    "update_version_body",
]
