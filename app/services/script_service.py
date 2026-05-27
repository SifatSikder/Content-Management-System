"""Script domain service.

Owns the script + version + comment + signoff loop for the script phase
of the pipeline. Mirrors `idea_service` semantics: each version is a
draft until the owner sends it for review, reviewers sign off
per-version, and locking requires every active reviewer's latest
signoff (across versions) to be `looks_good`. Locking advances the
project from `script_drafting` straight to `casting`. Permission
checks live in routes; these functions assume the caller has already
authorised the action.
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
from app.models.project import ProjectModel
from app.models.project_stage_assignment import ProjectStageAssignmentModel
from app.models.script import (
    ScriptCommentModel,
    ScriptModel,
    ScriptSignoffDecision,
    ScriptSignoffModel,
    ScriptVersionModel,
)
from app.models.user import UserModel
from app.services import (
    activity_service,
    assignment_service,
    email_service,
    project_service,
)

log = structlog.get_logger(__name__)


class ScriptVersionNotFoundError(Exception):
    """No version row matches the given id."""


class ScriptCommentNotFoundError(Exception):
    """No comment row matches the given id."""


class IllegalStageTransitionError(Exception):
    """The requested stage transition is not allowed from the current stage."""


class ScriptLockGateError(Exception):
    """Lock denied — not every reviewer has signed off on the latest version."""

    def __init__(self, pending_reviewer_ids: list[uuid.UUID]) -> None:
        super().__init__(
            f"{len(pending_reviewer_ids)} reviewer(s) still need to approve "
            "the latest version"
        )
        self.pending_reviewer_ids = pending_reviewer_ids


class ScriptVersionNotEditableError(Exception):
    """Cannot edit the version body in place — either the script is
    locked or reviewers have already signed off on this version."""


class ScriptVersionNotSubmittedError(Exception):
    """Cannot sign off on a version that hasn't been sent for review yet."""


class ScriptNotFoundError(Exception):
    """No script drafted yet for this project."""


class NoEnhancementReviewersError(Exception):
    """No reviewers picked / no eligible reviewers in the department."""


# ---------- script / version helpers ----------

async def _get_or_create_script(session: AsyncSession, project: ProjectModel) -> ScriptModel:
    result = await session.execute(select(ScriptModel).where(ScriptModel.project_id == project.id))
    script = result.scalar_one_or_none()
    if script is not None:
        return script
    script = ScriptModel(
        business_id=project.business_id, project_id=project.id
    )
    session.add(script)
    await session.flush()
    return script


async def get_script(
    session: AsyncSession, *, project: ProjectModel
) -> ScriptModel | None:
    result = await session.execute(
        select(ScriptModel).where(ScriptModel.project_id == project.id)
    )
    return result.scalar_one_or_none()


async def _next_version_number(session: AsyncSession, script_id: uuid.UUID) -> int:
    result = await session.execute(
        select(func.coalesce(func.max(ScriptVersionModel.version_number), 0)).where(
            ScriptVersionModel.script_id == script_id
        )
    )
    return int(result.scalar_one()) + 1


# ---------- versions ----------

async def add_version(
    session: AsyncSession,
    *,
    project: ProjectModel,
    author: UserModel,
    body_markdown: str,
) -> ScriptVersionModel:
    if project.script_locked_at is not None:
        raise IllegalStageTransitionError("Cannot add a version while the script is locked")

    script = await _get_or_create_script(session, project)
    version_number = await _next_version_number(session, script.id)
    version = ScriptVersionModel(
        business_id=project.business_id,
        script_id=script.id,
        version_number=version_number,
        body_markdown=body_markdown,
        author_id=author.id,
        # submitted_at intentionally null — a version becomes "submitted
        # for review" only when the owner explicitly clicks Request
        # feedback. Mirrors idea_service.
    )
    session.add(version)
    await session.flush()

    script.current_version_id = version.id

    await activity_service.record(
        session,
        project_id=project.id,
        actor_id=author.id,
        action="script.version_created",
        metadata={"version_number": version_number},
    )
    return version


async def list_versions(session: AsyncSession, *, project: ProjectModel) -> list[ScriptVersionModel]:
    result = await session.execute(
        select(ScriptVersionModel)
        .join(ScriptModel, ScriptModel.id == ScriptVersionModel.script_id)
        .where(ScriptModel.project_id == project.id)
        .order_by(ScriptVersionModel.version_number.asc())
    )
    return list(result.scalars().all())


async def latest_version(
    session: AsyncSession, *, project: ProjectModel
) -> ScriptVersionModel | None:
    result = await session.execute(
        select(ScriptVersionModel)
        .join(ScriptModel, ScriptModel.id == ScriptVersionModel.script_id)
        .where(ScriptModel.project_id == project.id)
        .order_by(ScriptVersionModel.version_number.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_version(session: AsyncSession, *, version_id: uuid.UUID) -> ScriptVersionModel:
    result = await session.execute(
        select(ScriptVersionModel).where(ScriptVersionModel.id == version_id)
    )
    version = result.scalar_one_or_none()
    if version is None:
        raise ScriptVersionNotFoundError(str(version_id))
    return version


async def update_version_body(
    session: AsyncSession,
    *,
    project: ProjectModel,
    version: ScriptVersionModel,
    actor: UserModel,
    body_markdown: str,
) -> ScriptVersionModel:
    """Edit the body of an existing script version in place. Allowed
    while the script is unlocked, the target is the LATEST version, and
    no reviewer has signed off on this version yet. Once a signoff
    lands the next edit has to be a new version so the reviewer's
    decision stays attached to the bytes they reviewed.
    """
    if project.script_locked_at is not None:
        raise ScriptVersionNotEditableError("Script is locked")
    latest = await latest_version(session, project=project)
    if latest is None or latest.id != version.id:
        raise ScriptVersionNotEditableError(
            "Only the latest version can be edited in place"
        )
    existing = await list_signoffs(session, version_id=version.id)
    if existing:
        raise ScriptVersionNotEditableError(
            "Reviewer(s) already signed off on this version — save a new "
            "version instead"
        )
    version.body_markdown = body_markdown
    await session.flush()
    await activity_service.record(
        session,
        project_id=project.id,
        actor_id=actor.id,
        action="script.version_edited",
        metadata={"version_number": version.version_number},
    )
    return version


# ---------- comments ----------

async def add_comment(
    session: AsyncSession,
    *,
    version: ScriptVersionModel,
    author: UserModel,
    body: str,
    paragraph_anchor: str | None = None,
) -> ScriptCommentModel:
    comment = ScriptCommentModel(
        business_id=version.business_id,
        version_id=version.id,
        author_id=author.id,
        body=body,
        paragraph_anchor=paragraph_anchor,
    )
    session.add(comment)
    await session.flush()

    # Find the project for the activity row (lazy lookup).
    script_result = await session.execute(
        select(ScriptModel).where(ScriptModel.id == version.script_id)
    )
    script = script_result.scalar_one()
    await activity_service.record(
        session,
        project_id=script.project_id,
        actor_id=author.id,
        action="script.comment_added",
        metadata={"version_number": version.version_number, "comment_id": str(comment.id)},
    )
    return comment


async def list_comments(
    session: AsyncSession, *, version_id: uuid.UUID
) -> list[ScriptCommentModel]:
    result = await session.execute(
        select(ScriptCommentModel)
        .where(ScriptCommentModel.version_id == version_id)
        .order_by(ScriptCommentModel.created_at.asc())
    )
    return list(result.scalars().all())


async def get_comment(session: AsyncSession, *, comment_id: uuid.UUID) -> ScriptCommentModel:
    result = await session.execute(
        select(ScriptCommentModel).where(ScriptCommentModel.id == comment_id)
    )
    comment = result.scalar_one_or_none()
    if comment is None:
        raise ScriptCommentNotFoundError(str(comment_id))
    return comment


async def resolve_comment(
    session: AsyncSession, *, comment: ScriptCommentModel, actor: UserModel
) -> ScriptCommentModel:
    if comment.resolved_at is None:
        comment.resolved_at = datetime.now(UTC)
        comment.resolved_by = actor.id

        version_result = await session.execute(
            select(ScriptVersionModel).where(ScriptVersionModel.id == comment.version_id)
        )
        version = version_result.scalar_one()
        script_result = await session.execute(
            select(ScriptModel).where(ScriptModel.id == version.script_id)
        )
        script = script_result.scalar_one()
        await activity_service.record(
            session,
            project_id=script.project_id,
            actor_id=actor.id,
            action="script.comment_resolved",
            metadata={"comment_id": str(comment.id)},
        )
    return comment


async def reopen_comment(
    session: AsyncSession, *, comment: ScriptCommentModel, actor: UserModel
) -> ScriptCommentModel:
    if comment.resolved_at is not None:
        comment.resolved_at = None
        comment.resolved_by = None
        version_result = await session.execute(
            select(ScriptVersionModel).where(ScriptVersionModel.id == comment.version_id)
        )
        version = version_result.scalar_one()
        script_result = await session.execute(
            select(ScriptModel).where(ScriptModel.id == version.script_id)
        )
        script = script_result.scalar_one()
        await activity_service.record(
            session,
            project_id=script.project_id,
            actor_id=actor.id,
            action="script.comment_reopened",
            metadata={"comment_id": str(comment.id)},
        )
    return comment


# ---------- signoffs ----------


async def list_signoffs(
    session: AsyncSession, *, version_id: uuid.UUID
) -> Sequence[ScriptSignoffModel]:
    result = await session.execute(
        select(ScriptSignoffModel)
        .where(ScriptSignoffModel.script_version_id == version_id)
        .order_by(ScriptSignoffModel.created_at.asc())
    )
    return list(result.scalars().all())


async def add_signoff(
    session: AsyncSession,
    *,
    project: ProjectModel,
    version: ScriptVersionModel,
    reviewer: UserModel,
    decision: ScriptSignoffDecision,
    comment: str | None,
) -> ScriptSignoffModel:
    if version.submitted_at is None:
        raise ScriptVersionNotSubmittedError(
            "This version is still a draft — the owner has to send it for "
            "review before reviewers can sign off"
        )
    row = ScriptSignoffModel(
        business_id=project.business_id,
        script_version_id=version.id,
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
        action="script.signoff",
        metadata={
            "version_number": version.version_number,
            "decision": decision.value,
        },
    )
    return row


async def latest_signoff_decision_by_user(
    session: AsyncSession, *, project: ProjectModel
) -> dict[uuid.UUID, ScriptSignoffDecision]:
    """For each reviewer who has ever signed off on any version of this
    project's script, return their most-recent decision (across
    versions). Used by the Request Feedback dialog to skip re-pinging
    people who already approved + by the lock gate's cross-version
    carry-over rule."""
    rows = await session.execute(
        select(ScriptSignoffModel)
        .join(
            ScriptVersionModel,
            ScriptVersionModel.id == ScriptSignoffModel.script_version_id,
        )
        .join(ScriptModel, ScriptModel.id == ScriptVersionModel.script_id)
        .where(ScriptModel.project_id == project.id)
        .order_by(ScriptSignoffModel.created_at.desc())
    )
    latest: dict[uuid.UUID, ScriptSignoffDecision] = {}
    for row in rows.scalars():
        if row.reviewer_id in latest:
            continue
        latest[row.reviewer_id] = row.decision
    return latest


# ---------- lock gate ----------


async def _active_reviewer_ids(
    session: AsyncSession, *, project: ProjectModel
) -> list[uuid.UUID]:
    """Active script_drafting assignees EXCLUDING the project owner —
    the owner is the author of the script and doesn't sign off on her
    own draft."""
    result = await session.execute(
        select(ProjectStageAssignmentModel.user_id)
        .where(ProjectStageAssignmentModel.project_id == project.id)
        .where(ProjectStageAssignmentModel.stage_key == "script_drafting")
        .where(ProjectStageAssignmentModel.removed_at.is_(None))
        .where(ProjectStageAssignmentModel.user_id != project.owner_id)
    )
    return [row[0] for row in result.all()]


async def lock_gate_status(
    session: AsyncSession, *, project: ProjectModel
) -> tuple[bool, list[uuid.UUID]]:
    """Return `(can_lock, pending_reviewer_ids)`.

    `can_lock = True` iff:
      * the latest version has been sent for review (`submitted_at` set), AND
      * every active script_drafting reviewer's *most recent* signoff across
        all versions is `LOOKS_GOOD`.

    The cross-version rule matches the "don't re-email approved
    reviewers" UX — once a director says looks-good, that carries
    forward to subsequent revisions unless they actively post a new
    `needs_changes`.
    """
    version = await latest_version(session, project=project)
    reviewers = await _active_reviewer_ids(session, project=project)
    if version is None or version.submitted_at is None:
        return False, reviewers
    if not reviewers:
        return True, []
    latest_by_user = await latest_signoff_decision_by_user(
        session, project=project
    )
    pending: list[uuid.UUID] = []
    for reviewer_id in reviewers:
        decision = latest_by_user.get(reviewer_id)
        if decision != ScriptSignoffDecision.LOOKS_GOOD:
            pending.append(reviewer_id)
    return (len(pending) == 0), pending


async def reviewer_count(
    session: AsyncSession, *, project: ProjectModel
) -> int:
    ids = await _active_reviewer_ids(session, project=project)
    return len(ids)


# ---------- request enhancement ----------


# Role keys whose holders get pulled in for script-enhancement feedback.
# Matches the idea flow exactly — CEO + Director hold the review hat.
_ENHANCEMENT_REVIEWER_ROLE_KEYS = ("ceo", "director", "junior_director")


async def list_enhancement_candidates(
    session: AsyncSession, *, project: ProjectModel
) -> list[tuple[uuid.UUID, str, str, str]]:
    """Return `(user_id, email, name, role_key)` for every dept member
    holding a CEO / Director role — the universe the owner can pick
    from when requesting script-enhancement feedback."""
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
    in the project's dept) to the `script_drafting` stage and email
    each one. Unticked previously-active reviewers are removed so the
    request list is authoritative.

    Returns the list of newly-assigned user ids.
    """
    latest = await latest_version(session, project=project)
    if latest is None:
        raise ScriptNotFoundError(
            "Save at least one draft version before requesting enhancement"
        )
    if not reviewer_user_ids:
        raise NoEnhancementReviewersError(
            "Pick at least one reviewer before requesting feedback"
        )
    # Stamp version submitted-for-review on first send. Re-sending later
    # doesn't reset the timestamp — first submission wins.
    if latest.submitted_at is None:
        latest.submitted_at = datetime.now(UTC)

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

    # Authoritative reviewer list: anyone the owner unticked gets pulled
    # off the stage assignment so the SignoffPanel + lock gate only
    # consider the people actually being asked. Historical signoffs stay
    # for the carry-over rule.
    requested_ids = set(reviewer_user_ids)
    current_ids = set(await _active_reviewer_ids(session, project=project))
    for stale_id in current_ids - requested_ids:
        try:
            await assignment_service.remove(
                session,
                project=project,
                stage_key="script_drafting",
                user_id=stale_id,
            )
        except assignment_service.AssignmentNotFoundError:
            pass

    newly_assigned: list[uuid.UUID] = []
    for user_id, _email, _name in reviewers:
        row = await assignment_service.add(
            session,
            project=project,
            stage_key="script_drafting",
            user_id=user_id,
            actor=actor,
        )
        if row.assigned_by == actor.id and row.removed_at is None:
            newly_assigned.append(user_id)

    await activity_service.record(
        session,
        project_id=project.id,
        actor_id=actor.id,
        action="script.enhancement_requested",
        metadata={"reviewer_count": len(reviewers)},
    )

    # Fire-and-forget email notifications. Don't let mail failures roll
    # back the assignment write.
    project_url = f"/projects/{project.id}"
    subject = f"Script feedback requested: {project.title}"
    html = (
        f"<p>{actor.name} asked for your feedback on the script for "
        f"<strong>{project.title}</strong>.</p>"
        f"<p>Open the project, switch to the <em>Script</em> tab, and either "
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
                "script_enhancement_email_skipped_not_configured",
                to=email,
                project_id=str(project.id),
            )
        except Exception as exc:
            log.warning(
                "script_enhancement_email_failed",
                to=email,
                project_id=str(project.id),
                error=str(exc),
            )

    return newly_assigned


# ---------- lock / unlock ----------

async def _advance_stage(
    session: AsyncSession,
    *,
    project: ProjectModel,
    target_key: str,
    actor_id: uuid.UUID,
) -> None:
    """Best-effort auto-advance to `target_key`. No-op if the target
    isn't in this template's stage list."""
    await project_service.auto_bump_stage(
        session, project=project, target_key=target_key, actor_id=actor_id
    )


async def lock_script(
    session: AsyncSession, *, project: ProjectModel, actor: UserModel
) -> ProjectModel:
    """Lock the script and advance to casting. Gated by
    `lock_gate_status` — every active reviewer's latest signoff
    (across versions) must be `looks_good` and the latest version must
    have been submitted for review.
    """
    if project.stage_key != "script_drafting":
        raise IllegalStageTransitionError(
            f"Cannot lock from stage {project.stage_key}"
        )
    if project.script_locked_at is not None:
        # Idempotent — already locked.
        return project
    can_lock, pending = await lock_gate_status(session, project=project)
    if not can_lock:
        raise ScriptLockGateError(pending)

    project.script_locked_at = datetime.now(UTC)
    project.script_locked_by = actor.id
    await _advance_stage(session, project=project, target_key="casting", actor_id=actor.id)

    await activity_service.record(
        session,
        project_id=project.id,
        actor_id=actor.id,
        action="script.locked",
    )
    return project


async def unlock_script(
    session: AsyncSession, *, project: ProjectModel, actor: UserModel
) -> ProjectModel:
    """Clear the script lock so the owner can edit / re-version.
    Symmetric to `lock_script`: if the project is currently on
    `casting` (just locked), roll the stage back to `script_drafting`.
    If work has progressed further (Shoot, Edit, …) leave the stage
    alone — the owner can drag it back manually if she actually wants
    to redo the script from scratch.
    """
    if project.script_locked_at is None:
        return project
    project.script_locked_at = None
    project.script_locked_by = None
    if project.stage_key == "casting":
        await _advance_stage(
            session,
            project=project,
            target_key="script_drafting",
            actor_id=actor.id,
        )
    await activity_service.record(
        session,
        project_id=project.id,
        actor_id=actor.id,
        action="script.unlocked",
    )
    return project


__all__ = [
    "IllegalStageTransitionError",
    "NoEnhancementReviewersError",
    "ScriptCommentNotFoundError",
    "ScriptLockGateError",
    "ScriptNotFoundError",
    "ScriptVersionNotEditableError",
    "ScriptVersionNotFoundError",
    "ScriptVersionNotSubmittedError",
    "add_comment",
    "add_signoff",
    "add_version",
    "get_comment",
    "get_script",
    "get_version",
    "latest_signoff_decision_by_user",
    "latest_version",
    "list_comments",
    "list_enhancement_candidates",
    "list_signoffs",
    "list_versions",
    "lock_gate_status",
    "lock_script",
    "reopen_comment",
    "request_enhancement",
    "resolve_comment",
    "reviewer_count",
    "unlock_script",
    "update_version_body",
]
