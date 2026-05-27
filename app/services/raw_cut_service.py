"""Raw-cut submission service — director uploads source material per
shoot during the `shooting` stage. Uploading cuts NO LONGER advances
the project — the director explicitly clicks "Shoot complete" once
every shoot is wrapped and every cut is in to bump the project to
`editing`. See `complete_shooting()` below."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models.department_membership import DepartmentMembershipModel
from app.models.department_role import DepartmentRoleModel
from app.models.project import ProjectModel
from app.models.project_stage_assignment import ProjectStageAssignmentModel
from app.models.raw_cut_submission import RawCutSubmissionModel
from app.models.user import UserModel
from app.services import activity_service, email_service, project_service

log = structlog.get_logger(__name__)


class RawCutSubmissionNotFoundError(Exception):
    """Raw-cut submission does not exist."""


class IllegalShootingCompleteError(Exception):
    """`complete_shooting` called from a stage other than `shooting`."""


async def submit_raw_cut(
    session: AsyncSession,
    *,
    project: ProjectModel,
    shoot_id: uuid.UUID,
    uploader: UserModel,
    gcs_bucket: str,
    gcs_object_name: str,
    content_type: str | None,
    byte_size: int | None,
    original_filename: str | None,
) -> RawCutSubmissionModel:
    row = RawCutSubmissionModel(
        business_id=project.business_id,
        project_id=project.id,
        shoot_id=shoot_id,
        uploader_id=uploader.id,
        gcs_bucket=gcs_bucket,
        gcs_object_name=gcs_object_name,
        content_type=content_type,
        byte_size=byte_size,
        original_filename=original_filename,
        submitted_at=datetime.now(UTC),
    )
    session.add(row)
    await session.flush()

    await activity_service.record(
        session,
        project_id=project.id,
        actor_id=uploader.id,
        action="raw_cut.submitted",
        metadata={
            "raw_cut_id": str(row.id),
            "object_name": gcs_object_name,
            "byte_size": byte_size,
        },
    )
    return row


async def list_raw_cuts(
    session: AsyncSession, *, project_id: uuid.UUID
) -> Sequence[RawCutSubmissionModel]:
    result = await session.execute(
        select(RawCutSubmissionModel)
        .where(RawCutSubmissionModel.project_id == project_id)
        .options(selectinload(RawCutSubmissionModel.uploader))
        .order_by(RawCutSubmissionModel.submitted_at.asc())
    )
    return list(result.scalars().all())


async def get_raw_cut(
    session: AsyncSession, *, raw_cut_id: uuid.UUID
) -> RawCutSubmissionModel:
    row = await session.get(RawCutSubmissionModel, raw_cut_id)
    if row is None:
        raise RawCutSubmissionNotFoundError(str(raw_cut_id))
    return row


async def complete_shooting(
    session: AsyncSession,
    *,
    project: ProjectModel,
    actor: UserModel,
) -> ProjectModel:
    """Explicitly advance the project from `shooting` to `editing`.

    Director-triggered (dual-confirmed in the UI) — there's no longer
    an automatic transition off the first raw-cut upload, since a
    single project can have multiple shoots each with their own cuts.
    Idempotent on calls from `editing` or beyond (just records an
    activity row and returns).

    Emails are fired after the stage advance:
      * the editor(s) auto-assigned to `editing` get an urgent
        "start editing ASAP" nudge,
      * CEO + Assistant CEO (resolved by role on the department) get
        a heads-up status update.
    """
    if project.stage_key != "shooting":
        raise IllegalShootingCompleteError(
            f"Cannot complete shooting from stage {project.stage_key}"
        )
    await project_service.auto_bump_stage(
        session, project=project, target_key="editing", actor_id=actor.id
    )
    await activity_service.record(
        session,
        project_id=project.id,
        actor_id=actor.id,
        action="shooting.completed",
    )
    await _notify_editing_kickoff(session, project=project, actor=actor)
    return project


# Roles that get the heads-up email when shooting completes. Both
# legacy template keys and the user-renamed equivalent are listed so
# departments running either wiring still notify the right people.
_LEADERSHIP_ROLE_KEYS = ("ceo", "assistant_director", "assistant_ceo")
_EDITOR_ROLE_KEYS = ("editor",)


async def _notify_editing_kickoff(
    session: AsyncSession, *, project: ProjectModel, actor: UserModel
) -> None:
    """Fire the kickoff emails. Failures are swallowed — the stage
    advance is the source of truth, mail is best-effort."""
    settings = get_settings()
    project_url = f"{settings.app_base_url.rstrip('/')}/projects/{project.id}"

    # Editor(s) — active assignees on the editing stage, which
    # `seed_default` just populated from the handoff config.
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
    editor_recipients = list(editor_rows.all())

    editor_subject = f"🎬 Raw cuts ready — start editing: {project.title}"
    editor_html = (
        f"<p><strong>{actor.name} just marked shooting complete on "
        f"<em>{project.title}</em>.</strong></p>"
        f"<p>The raw cuts are uploaded and waiting for you. Please pick "
        f"this up as soon as you can — the team is blocked on your first "
        f"edit.</p>"
        f"<p><a href=\"{project_url}\">Open the project to start</a></p>"
    )
    for email, _name in editor_recipients:
        await _safe_send(email, editor_subject, editor_html, project.id)

    # Leadership (CEO + Asst CEO) — resolved by dept role membership.
    # Excludes anyone who already received the editor email above so
    # they don't get double-pinged in the (unlikely) case roles overlap.
    editor_emails = {e for e, _n in editor_recipients}
    leadership_rows = await session.execute(
        select(UserModel.email, UserModel.name)
        .join(
            DepartmentMembershipModel,
            DepartmentMembershipModel.user_id == UserModel.id,
        )
        .join(
            DepartmentRoleModel,
            DepartmentRoleModel.id == DepartmentMembershipModel.role_id,
        )
        .where(DepartmentMembershipModel.department_id == project.department_id)
        .where(DepartmentRoleModel.key.in_(_LEADERSHIP_ROLE_KEYS))
    )
    leadership_recipients = [
        (e, n) for e, n in leadership_rows.all() if e not in editor_emails
    ]

    leadership_subject = f"Update: {project.title} is now in Editing"
    leadership_html = (
        f"<p>{actor.name} marked all shooting complete on "
        f"<strong>{project.title}</strong>. The project has moved to "
        f"<em>Editing</em>; the editor has been notified to pick up the "
        f"raw cuts.</p>"
        f"<p><a href=\"{project_url}\">Open the project</a></p>"
    )
    for email, _name in leadership_recipients:
        await _safe_send(email, leadership_subject, leadership_html, project.id)


async def _safe_send(
    to: str, subject: str, html: str, project_id: uuid.UUID
) -> None:
    try:
        await email_service.send_html_email(to=to, subject=subject, html=html)
    except email_service.EmailNotConfiguredError:
        log.info(
            "editing_kickoff_email_skipped_not_configured",
            to=to,
            project_id=str(project_id),
        )
    except Exception as exc:
        log.warning(
            "editing_kickoff_email_failed",
            to=to,
            project_id=str(project_id),
            error=str(exc),
        )


__all__ = [
    "IllegalShootingCompleteError",
    "RawCutSubmissionNotFoundError",
    "complete_shooting",
    "get_raw_cut",
    "list_raw_cuts",
    "submit_raw_cut",
]
