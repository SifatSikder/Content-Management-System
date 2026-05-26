"""Edit-version domain service.

Manages the upload → review → approve lifecycle for video cuts. The frontend
uploads the bytes directly to GCS (via a resumable session URL minted by
`storage_service`); this service tracks the metadata, status, and pipeline
stage transitions.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.edit import EditCommentModel, EditVersionModel
from app.models.enums import EditStatus, Role
from app.models.project import ProjectModel
from app.models.user import UserModel
from app.services import activity_service, project_service

log = structlog.get_logger(__name__)


class EditNotFoundError(Exception):
    """No edit version matches the given id."""


class EditCommentNotFoundError(Exception):
    """No edit comment matches the given id."""


class IllegalEditTransitionError(Exception):
    """Approve / request-changes called on an edit in a wrong status."""


async def _advance_stage(
    session: AsyncSession,
    *,
    project: ProjectModel,
    target_key: str,
    actor_id: uuid.UUID,
) -> None:
    """Resolve `target_key` to a stage_id inside `project.department_id` and
    move the project there. No-op if the target key doesn't exist in the
    department (other templates may not model this transition)."""
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
    version_number = await _next_version_number(session, project.id)
    edit = EditVersionModel(
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
    return edit


async def approve_edit(
    session: AsyncSession,
    *,
    edit: EditVersionModel,
    project: ProjectModel,
    actor: UserModel,
) -> EditVersionModel:
    """Approve a cut. CEO can publish from here; others mark approved-in-review."""
    if edit.status == EditStatus.APPROVED:
        return edit
    edit.status = EditStatus.APPROVED
    edit.approved_at = datetime.now(UTC)
    edit.approved_by = actor.id

    metadata: dict[str, object] = {"version_number": edit.version_number}

    # CEO approval → "approved_published" (terminal stage). Anyone else's
    # approve just records the decision without moving the project.
    if actor.role == Role.CEO and project.stage_key != "approved_published":
        await _advance_stage(
            session, project=project, target_key="approved_published", actor_id=actor.id
        )
        metadata["published"] = True

    await activity_service.record(
        session,
        project_id=project.id,
        actor_id=actor.id,
        action="edit.approved",
        metadata=metadata,
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
    if edit.status == EditStatus.APPROVED:
        raise IllegalEditTransitionError("Cannot request changes on an approved cut")
    edit.status = EditStatus.CHANGES_REQUESTED
    # The reviewer's note replaces any prior request note. Multiple iterations
    # are tracked via subsequent edit versions, not by appending here.
    edit.notes = notes

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
    comment = EditCommentModel(
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
    "add_edit_comment",
    "add_edit_version",
    "approve_edit",
    "get_edit",
    "get_edit_comment",
    "list_edit_comments",
    "list_edits_for_project",
    "reopen_edit_comment",
    "request_changes",
    "resolve_edit_comment",
]
