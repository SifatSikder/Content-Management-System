"""Raw-cut submission service — director uploads the raw cuts at end of
`shoot_done`, the first submission auto-advances the project to `editing`."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.project import ProjectModel
from app.models.raw_cut_submission import RawCutSubmissionModel
from app.models.user import UserModel
from app.services import activity_service, project_service

log = structlog.get_logger(__name__)


class RawCutSubmissionNotFoundError(Exception):
    """Raw-cut submission does not exist."""


async def submit_raw_cut(
    session: AsyncSession,
    *,
    project: ProjectModel,
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

    # First submission of raw cuts pushes the project from shoot_done → editing
    # so the editor can pick them up. No-op if already past shoot_done.
    if project.stage_key == "shoot_done":
        await project_service.auto_bump_stage(
            session, project=project, target_key="editing", actor_id=uploader.id
        )

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


__all__ = [
    "RawCutSubmissionNotFoundError",
    "get_raw_cut",
    "list_raw_cuts",
    "submit_raw_cut",
]
