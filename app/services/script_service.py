"""Script domain service.

Owns the script + version + comment + stage-transition logic for the script
phase of the pipeline. Permission checks live in routes/dependencies — these
functions assume the caller has already authorised the action.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PipelineStage
from app.models.project import ProjectModel
from app.models.script import ScriptCommentModel, ScriptModel, ScriptVersionModel
from app.models.user import UserModel
from app.services import activity_service

log = structlog.get_logger(__name__)


class ScriptVersionNotFoundError(Exception):
    """No version row matches the given id."""


class ScriptCommentNotFoundError(Exception):
    """No comment row matches the given id."""


class IllegalStageTransitionError(Exception):
    """The requested stage transition is not allowed from the current stage."""


# ---------- script / version helpers ----------

async def _get_or_create_script(session: AsyncSession, project: ProjectModel) -> ScriptModel:
    result = await session.execute(select(ScriptModel).where(ScriptModel.project_id == project.id))
    script = result.scalar_one_or_none()
    if script is not None:
        return script
    script = ScriptModel(project_id=project.id)
    session.add(script)
    await session.flush()
    return script


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
    if project.stage == PipelineStage.SCRIPT_LOCKED:
        raise IllegalStageTransitionError("Cannot add a version while the script is locked")

    script = await _get_or_create_script(session, project)
    version_number = await _next_version_number(session, script.id)
    version = ScriptVersionModel(
        script_id=script.id,
        version_number=version_number,
        body_markdown=body_markdown,
        author_id=author.id,
    )
    session.add(version)
    await session.flush()

    script.current_version_id = version.id

    # First version moves the project past IDEA/CATEGORY_SET into SCRIPT_DRAFTING.
    if project.stage in (PipelineStage.IDEA, PipelineStage.CATEGORY_SET):
        previous = project.stage
        project.stage = PipelineStage.SCRIPT_DRAFTING
        await activity_service.record(
            session,
            project_id=project.id,
            actor_id=author.id,
            action="project.stage_changed",
            metadata={"from": previous.value, "to": PipelineStage.SCRIPT_DRAFTING.value},
        )

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


async def get_version(session: AsyncSession, *, version_id: uuid.UUID) -> ScriptVersionModel:
    result = await session.execute(
        select(ScriptVersionModel).where(ScriptVersionModel.id == version_id)
    )
    version = result.scalar_one_or_none()
    if version is None:
        raise ScriptVersionNotFoundError(str(version_id))
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


# ---------- stage transitions ----------

async def submit_script(
    session: AsyncSession, *, project: ProjectModel, actor: UserModel
) -> ProjectModel:
    if project.stage != PipelineStage.SCRIPT_DRAFTING:
        raise IllegalStageTransitionError(
            f"Cannot submit from stage {project.stage.value}"
        )
    # Mark the latest version as submitted.
    result = await session.execute(
        select(ScriptVersionModel)
        .join(ScriptModel, ScriptModel.id == ScriptVersionModel.script_id)
        .where(ScriptModel.project_id == project.id)
        .order_by(ScriptVersionModel.version_number.desc())
        .limit(1)
    )
    latest = result.scalar_one_or_none()
    if latest is not None and latest.submitted_at is None:
        latest.submitted_at = datetime.now(UTC)

    project.stage = PipelineStage.SCRIPT_REVIEW
    await activity_service.record(
        session,
        project_id=project.id,
        actor_id=actor.id,
        action="script.submitted",
        metadata={"to": PipelineStage.SCRIPT_REVIEW.value},
    )
    return project


async def lock_script(
    session: AsyncSession, *, project: ProjectModel, actor: UserModel
) -> ProjectModel:
    if project.stage not in (PipelineStage.SCRIPT_DRAFTING, PipelineStage.SCRIPT_REVIEW):
        raise IllegalStageTransitionError(
            f"Cannot lock from stage {project.stage.value}"
        )
    project.stage = PipelineStage.SCRIPT_LOCKED
    project.script_locked_at = datetime.now(UTC)
    project.script_locked_by = actor.id

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
    if project.stage != PipelineStage.SCRIPT_LOCKED:
        raise IllegalStageTransitionError(
            f"Cannot unlock from stage {project.stage.value}"
        )
    project.stage = PipelineStage.SCRIPT_REVIEW
    project.script_locked_at = None
    project.script_locked_by = None
    await activity_service.record(
        session,
        project_id=project.id,
        actor_id=actor.id,
        action="script.unlocked",
    )
    return project


__all__ = [
    "IllegalStageTransitionError",
    "ScriptCommentNotFoundError",
    "ScriptVersionNotFoundError",
    "add_comment",
    "add_version",
    "get_comment",
    "get_version",
    "list_comments",
    "list_versions",
    "lock_script",
    "reopen_comment",
    "resolve_comment",
    "submit_script",
    "unlock_script",
]
