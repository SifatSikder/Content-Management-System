"""Edit-version domain service.

Manages the upload → review → approve lifecycle for video cuts. The
frontend uploads bytes directly to GCS (via a resumable session URL
minted by `storage_service`); this service tracks metadata, status,
per-reviewer approvals, and the pipeline stage transition to
`approved_published`.

The approval model is dual-reviewer: the project's required approvers
(everyone in the dept holding `asset_review_with_timecodes.approve`)
must each insert a row in `edit_approvals` pointing at the latest
version before the project advances to `approved_published`.
`request_changes` is still a single per-version action that bumps the
project back to `editing` so the editor can iterate.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.department_membership import DepartmentMembershipModel
from app.models.department_role import DepartmentRoleModel
from app.models.department_role_permission import DepartmentRolePermissionModel
from app.models.edit import EditApprovalModel, EditCommentModel, EditVersionModel
from app.models.enums import EditStatus
from app.models.project import ProjectModel
from app.models.project_stage_assignment import ProjectStageAssignmentModel
from app.models.user import UserModel
from app.services import activity_service, email_service, project_service

log = structlog.get_logger(__name__)


class EditNotFoundError(Exception):
    """No edit version matches the given id."""


class EditCommentNotFoundError(Exception):
    """No edit comment matches the given id."""


class IllegalEditTransitionError(Exception):
    """Approve / request-changes called on an edit in a wrong status."""


class ProjectFinalisedError(Exception):
    """The project is on `approved_published`; no further writes allowed."""


_APPROVE_ACTION_KEY = "asset_review_with_timecodes.approve"


def _ensure_not_finalised(project: ProjectModel) -> None:
    if project.stage_key == "approved_published":
        raise ProjectFinalisedError(
            "Project is approved & published — no further edit changes are allowed"
        )


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


async def _next_version_number(session: AsyncSession, project_id: uuid.UUID) -> int:
    result = await session.execute(
        select(func.coalesce(func.max(EditVersionModel.version_number), 0)).where(
            EditVersionModel.project_id == project_id
        )
    )
    return int(result.scalar_one()) + 1


async def get_edit(session: AsyncSession, *, edit_id: uuid.UUID) -> EditVersionModel:
    result = await session.execute(select(EditVersionModel).where(EditVersionModel.id == edit_id))
    edit = result.scalar_one_or_none()
    if edit is None:
        raise EditNotFoundError(str(edit_id))
    return edit


async def latest_version(
    session: AsyncSession, *, project_id: uuid.UUID
) -> EditVersionModel | None:
    result = await session.execute(
        select(EditVersionModel)
        .where(EditVersionModel.project_id == project_id)
        .order_by(EditVersionModel.version_number.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


# ---------- required approvers + approval gate ----------


async def required_approver_ids(
    session: AsyncSession, *, project: ProjectModel
) -> list[uuid.UUID]:
    """Every dept member whose role holds the
    `asset_review_with_timecodes.approve` permission. Used as the
    "must-approve" set for the dual-reviewer gate. CEO + Asst CEO in
    the live setup; mirrors the seed."""
    result = await session.execute(
        select(DepartmentMembershipModel.user_id)
        .join(
            DepartmentRoleModel,
            DepartmentRoleModel.id == DepartmentMembershipModel.role_id,
        )
        .join(
            DepartmentRolePermissionModel,
            DepartmentRolePermissionModel.department_role_id == DepartmentRoleModel.id,
        )
        .where(DepartmentMembershipModel.department_id == project.department_id)
        .where(DepartmentRolePermissionModel.action_key == _APPROVE_ACTION_KEY)
        .where(DepartmentRolePermissionModel.allowed.is_(True))
        .distinct()
    )
    return [row[0] for row in result.all()]


async def list_approvals(
    session: AsyncSession, *, edit_version_id: uuid.UUID
) -> list[EditApprovalModel]:
    result = await session.execute(
        select(EditApprovalModel)
        .where(EditApprovalModel.edit_version_id == edit_version_id)
        .order_by(EditApprovalModel.created_at.asc())
    )
    return list(result.scalars().all())


async def approval_gate_status(
    session: AsyncSession, *, edit: EditVersionModel, project: ProjectModel
) -> tuple[bool, list[uuid.UUID]]:
    """Return `(can_publish, pending_reviewer_ids)` for the version's
    current approvals. `can_publish=True` iff every required approver
    has a row on THIS version. Per-version semantics — V1 approvals
    don't carry to V2."""
    required = set(await required_approver_ids(session, project=project))
    if not required:
        # Misconfigured dept — no one can approve. Don't auto-publish.
        return False, []
    approved_rows = await session.execute(
        select(EditApprovalModel.reviewer_id).where(
            EditApprovalModel.edit_version_id == edit.id
        )
    )
    approved = {row[0] for row in approved_rows.all()}
    pending = list(required - approved)
    return (not pending), pending


# ---------- versions ----------


async def add_edit_version(
    session: AsyncSession,
    *,
    project: ProjectModel,
    uploader: UserModel,
    gcs_bucket: str,
    gcs_object_name: str,
    content_type: str,
    size_bytes: int,
    notes: str | None = None,
    resolved_comments: list[uuid.UUID] | None = None,
) -> EditVersionModel:
    _ensure_not_finalised(project)
    version_number = await _next_version_number(session, project.id)
    edit = EditVersionModel(
        business_id=project.business_id,
        project_id=project.id,
        version_number=version_number,
        uploader_id=uploader.id,
        gcs_bucket=gcs_bucket,
        gcs_object_name=gcs_object_name,
        content_type=content_type,
        size_bytes=size_bytes,
        status=EditStatus.IN_REVIEW,
        notes=notes,
        resolved_comments=[str(cid) for cid in (resolved_comments or [])],
    )
    session.add(edit)
    await session.flush()

    # First edit upload advances the project to "editing".
    if project.stage_key not in ("editing", "edit_review", "approved_published"):
        await _advance_stage(session, project=project, target_key="editing", actor_id=uploader.id)

    await activity_service.record(
        session,
        project_id=project.id,
        actor_id=uploader.id,
        action="edit.uploaded",
        metadata={
            "version_number": version_number,
            "size_bytes": size_bytes,
            "resolved_comments_count": len(resolved_comments or []),
        },
    )
    await _notify_reviewers_of_new_cut(
        session, project=project, edit=edit, uploader=uploader
    )
    return edit


# ---------- approve / request-changes ----------


async def approve_edit(
    session: AsyncSession,
    *,
    edit: EditVersionModel,
    project: ProjectModel,
    actor: UserModel,
) -> EditVersionModel:
    """Record an approval row for `actor` on this version. If the
    latest version is fully approved (every required reviewer has a
    row), flip the version's status to APPROVED, stamp `approved_at/by`
    with the closing reviewer, and advance the project to
    `approved_published`.
    """
    _ensure_not_finalised(project)
    # Verify actor is a required approver — silently accepting clicks
    # from non-reviewers would muddy the gate.
    required = set(await required_approver_ids(session, project=project))
    if actor.id not in required and not actor.is_super_admin:
        raise IllegalEditTransitionError(
            "You are not configured as an approver for this project"
        )

    # Idempotent insert — upsert via "skip if exists" SELECT.
    existing = await session.execute(
        select(EditApprovalModel.id)
        .where(EditApprovalModel.edit_version_id == edit.id)
        .where(EditApprovalModel.reviewer_id == actor.id)
        .limit(1)
    )
    if existing.first() is None:
        session.add(
            EditApprovalModel(
                business_id=project.business_id,
                edit_version_id=edit.id,
                reviewer_id=actor.id,
            )
        )
        await session.flush()
        await activity_service.record(
            session,
            project_id=project.id,
            actor_id=actor.id,
            action="edit.approval_added",
            metadata={"version_number": edit.version_number},
        )

    can_publish, _pending = await approval_gate_status(
        session, edit=edit, project=project
    )
    if can_publish:
        edit.status = EditStatus.APPROVED
        edit.approved_at = datetime.now(UTC)
        edit.approved_by = actor.id
        if project.stage_key != "approved_published":
            await _advance_stage(
                session,
                project=project,
                target_key="approved_published",
                actor_id=actor.id,
            )
        await activity_service.record(
            session,
            project_id=project.id,
            actor_id=actor.id,
            action="edit.published",
            metadata={"version_number": edit.version_number},
        )
    return edit


async def request_changes(
    session: AsyncSession,
    *,
    edit: EditVersionModel,
    project: ProjectModel,
    actor: UserModel,
    notes: str,
) -> EditVersionModel:
    _ensure_not_finalised(project)
    if edit.status == EditStatus.APPROVED:
        raise IllegalEditTransitionError("Cannot request changes on an approved cut")
    edit.status = EditStatus.CHANGES_REQUESTED
    # The reviewer's note replaces any prior request note. Multiple iterations
    # are tracked via subsequent edit versions, not by appending here.
    edit.notes = notes

    # Wipe any prior approvals on this version — the editor will deliver
    # a new version that everyone needs to re-approve from scratch.
    # Approvals carry the version_id so they stay attached to the bytes
    # they were given to, but for this current version they're stale.
    await session.execute(
        delete(EditApprovalModel).where(
            EditApprovalModel.edit_version_id == edit.id
        )
    )

    # Make sure the project is in "editing" so the editor can upload V+1.
    if project.stage_key != "editing":
        await _advance_stage(session, project=project, target_key="editing", actor_id=actor.id)

    await activity_service.record(
        session,
        project_id=project.id,
        actor_id=actor.id,
        action="edit.changes_requested",
        metadata={"version_number": edit.version_number, "notes_length": len(notes)},
    )
    return edit


async def list_edits_for_project(
    session: AsyncSession, *, project_id: uuid.UUID
) -> list[EditVersionModel]:
    result = await session.execute(
        select(EditVersionModel)
        .where(EditVersionModel.project_id == project_id)
        .order_by(EditVersionModel.version_number.asc())
    )
    return list(result.scalars().all())


# ---------- email on new cut upload ----------


async def _notify_reviewers_of_new_cut(
    session: AsyncSession,
    *,
    project: ProjectModel,
    edit: EditVersionModel,
    uploader: UserModel,
) -> None:
    """Email every required approver that a new cut version is ready
    for review. Failures are swallowed — the upload is the source of
    truth."""
    required = await required_approver_ids(session, project=project)
    if not required:
        return
    rows = await session.execute(
        select(UserModel.email, UserModel.name).where(UserModel.id.in_(required))
    )
    recipients = [(e, n) for e, n in rows.all() if e]
    if not recipients:
        return

    settings = get_settings()
    project_url = f"{settings.app_base_url.rstrip('/')}/projects/{project.id}"
    subject = f"New cut ready for review (V{edit.version_number}): {project.title}"
    html = (
        f"<p>{uploader.name} just uploaded "
        f"<strong>V{edit.version_number}</strong> of "
        f"<em>{project.title}</em>.</p>"
        f"<p>Open the Edits tab, play through the cut, drop timestamped "
        f"comments if needed, and approve or request changes.</p>"
        f"<p><a href=\"{project_url}\">Review the cut</a></p>"
    )
    for email, _name in recipients:
        try:
            await email_service.send_html_email(
                to=email, subject=subject, html=html
            )
        except email_service.EmailNotConfiguredError:
            log.info(
                "edit_review_email_skipped_not_configured",
                to=email,
                project_id=str(project.id),
            )
        except Exception as exc:
            log.warning(
                "edit_review_email_failed",
                to=email,
                project_id=str(project.id),
                error=str(exc),
            )


# ---------- timestamped comments on a cut ----------

async def add_edit_comment(
    session: AsyncSession,
    *,
    edit: EditVersionModel,
    project: ProjectModel,
    author: UserModel,
    body: str,
    timestamp_seconds: float,
) -> EditCommentModel:
    _ensure_not_finalised(project)
    comment = EditCommentModel(
        business_id=project.business_id,
        edit_version_id=edit.id,
        author_id=author.id,
        timestamp_seconds=timestamp_seconds,
        body=body,
    )
    session.add(comment)
    await session.flush()
    await activity_service.record(
        session,
        project_id=project.id,
        actor_id=author.id,
        action="edit.comment_added",
        metadata={
            "version_number": edit.version_number,
            "timestamp_seconds": timestamp_seconds,
            "comment_id": str(comment.id),
        },
    )
    return comment


async def list_edit_comments(
    session: AsyncSession, *, edit_version_id: uuid.UUID
) -> list[EditCommentModel]:
    result = await session.execute(
        select(EditCommentModel)
        .where(EditCommentModel.edit_version_id == edit_version_id)
        .order_by(EditCommentModel.timestamp_seconds.asc())
    )
    return list(result.scalars().all())


async def dispatch_comments(
    session: AsyncSession,
    *,
    edit: EditVersionModel,
    project: ProjectModel,
    reviewer: UserModel,
) -> int:
    """Stamp `sent_at = now()` on every undispatched comment this
    reviewer has on this cut version, then email the editor about the
    batch. Returns the count dispatched (0 if there was nothing to
    send). Idempotent.
    """
    _ensure_not_finalised(project)
    now = datetime.now(UTC)
    result = await session.execute(
        update(EditCommentModel)
        .where(EditCommentModel.edit_version_id == edit.id)
        .where(EditCommentModel.author_id == reviewer.id)
        .where(EditCommentModel.sent_at.is_(None))
        .values(sent_at=now)
        .returning(EditCommentModel.id)
    )
    dispatched_ids = [row[0] for row in result.all()]
    count = len(dispatched_ids)
    if count == 0:
        return 0

    await activity_service.record(
        session,
        project_id=project.id,
        actor_id=reviewer.id,
        action="edit.comments_dispatched",
        metadata={
            "version_number": edit.version_number,
            "count": count,
        },
    )
    await _notify_editor_of_feedback(
        session,
        project=project,
        edit=edit,
        reviewer=reviewer,
        comment_count=count,
    )
    return count


async def _notify_editor_of_feedback(
    session: AsyncSession,
    *,
    project: ProjectModel,
    edit: EditVersionModel,
    reviewer: UserModel,
    comment_count: int,
) -> None:
    """Email every active assignee on the editing stage (= the editor)
    that a batch of timestamped feedback just came in."""
    editor_rows = await session.execute(
        select(UserModel.email, UserModel.name)
        .join(
            ProjectStageAssignmentModel,
            ProjectStageAssignmentModel.user_id == UserModel.id,
        )
        .where(ProjectStageAssignmentModel.project_id == project.id)
        .where(ProjectStageAssignmentModel.stage_key == "editing")
        .where(ProjectStageAssignmentModel.removed_at.is_(None))
    )
    recipients = [(e, n) for e, n in editor_rows.all() if e]
    if not recipients:
        return

    settings = get_settings()
    project_url = (
        f"{settings.app_base_url.rstrip('/')}/projects/{project.id}"
    )
    subject = (
        f"New feedback on V{edit.version_number}: {project.title} "
        f"({comment_count} comment{'s' if comment_count != 1 else ''})"
    )
    html = (
        f"<p><strong>{reviewer.name} just sent {comment_count} timestamped "
        f"comment{'s' if comment_count != 1 else ''} on V{edit.version_number} "
        f"of <em>{project.title}</em>.</strong></p>"
        f"<p>Open the Edits tab, jump through the timeline to each note, and "
        f"upload a revised cut when you've addressed them.</p>"
        f"<p><a href=\"{project_url}\">Open the project</a></p>"
    )
    for email, _name in recipients:
        try:
            await email_service.send_html_email(
                to=email, subject=subject, html=html
            )
        except email_service.EmailNotConfiguredError:
            log.info(
                "edit_feedback_email_skipped_not_configured",
                to=email,
                project_id=str(project.id),
            )
        except Exception as exc:
            log.warning(
                "edit_feedback_email_failed",
                to=email,
                project_id=str(project.id),
                error=str(exc),
            )


async def get_edit_comment(
    session: AsyncSession, *, comment_id: uuid.UUID
) -> EditCommentModel:
    result = await session.execute(
        select(EditCommentModel).where(EditCommentModel.id == comment_id)
    )
    comment = result.scalar_one_or_none()
    if comment is None:
        raise EditCommentNotFoundError(str(comment_id))
    return comment


async def resolve_edit_comment(
    session: AsyncSession,
    *,
    comment: EditCommentModel,
    project: ProjectModel,
    actor: UserModel,
) -> EditCommentModel:
    _ensure_not_finalised(project)
    if comment.resolved_at is None:
        comment.resolved_at = datetime.now(UTC)
        comment.resolved_by = actor.id
        await activity_service.record(
            session,
            project_id=project.id,
            actor_id=actor.id,
            action="edit.comment_resolved",
            metadata={"comment_id": str(comment.id)},
        )
    return comment


async def reopen_edit_comment(
    session: AsyncSession,
    *,
    comment: EditCommentModel,
    project: ProjectModel,
    actor: UserModel,
) -> EditCommentModel:
    _ensure_not_finalised(project)
    if comment.resolved_at is not None:
        comment.resolved_at = None
        comment.resolved_by = None
        await activity_service.record(
            session,
            project_id=project.id,
            actor_id=actor.id,
            action="edit.comment_reopened",
            metadata={"comment_id": str(comment.id)},
        )
    return comment


__all__ = [
    "EditCommentNotFoundError",
    "EditNotFoundError",
    "IllegalEditTransitionError",
    "ProjectFinalisedError",
    "add_edit_comment",
    "add_edit_version",
    "approval_gate_status",
    "approve_edit",
    "dispatch_comments",
    "get_edit",
    "get_edit_comment",
    "latest_version",
    "list_approvals",
    "list_edit_comments",
    "list_edits_for_project",
    "reopen_edit_comment",
    "request_changes",
    "required_approver_ids",
    "resolve_edit_comment",
]
