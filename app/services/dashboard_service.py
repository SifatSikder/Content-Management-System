"""Dashboard aggregations (Phase 3 Task 3.2).

Pure read-side queries over `projects`, `edit_versions`, and `activities`. No
mutations, no permissions — routes gate access. All times are computed in UTC.

Five summaries:
    awaiting()         — final cuts waiting on approval
    stage_counts()     — histogram across the 11 pipeline stages
    stuck(threshold)   — projects with no activity for ≥ N days
    throughput(weeks)  — projects published per ISO week
    time_in_stage()    — average + max days spent per stage

The dashboard is intentionally small — a few SELECTs across already-indexed
columns. We avoid materialised views or background recompute.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import ActivityModel
from app.models.edit import EditVersionModel
from app.models.enums import EditStatus, PipelineStage
from app.models.project import ProjectModel
from app.models.user import UserModel

log = structlog.get_logger(__name__)


# ---------- DTOs ----------


@dataclass(frozen=True)
class AwaitingItem:
    project_id: uuid.UUID
    project_title: str
    stage: PipelineStage
    cut_id: uuid.UUID
    cut_version: int
    uploaded_at: datetime
    uploader_id: uuid.UUID | None


@dataclass(frozen=True)
class StageCount:
    stage: PipelineStage
    count: int


@dataclass(frozen=True)
class StuckProject:
    project_id: uuid.UUID
    project_title: str
    stage: PipelineStage
    owner_id: uuid.UUID
    owner_name: str
    last_activity_at: datetime | None
    days_idle: int


@dataclass(frozen=True)
class ThroughputBucket:
    """One ISO week of published projects. `week_start` is the Monday UTC."""

    week_start: datetime
    count: int


@dataclass(frozen=True)
class TimeInStage:
    stage: PipelineStage
    sample_size: int
    avg_days: float | None
    max_days: float | None


# ---------- 1. awaiting ----------


async def awaiting(session: AsyncSession) -> list[AwaitingItem]:
    """Cuts whose status is still IN_REVIEW — the CEO's approval queue.

    Excludes soft-deleted projects. Ordered newest-uploaded first so the
    freshly-pinged item lands at the top.
    """
    q = (
        select(EditVersionModel, ProjectModel)
        .join(ProjectModel, ProjectModel.id == EditVersionModel.project_id)
        .where(
            EditVersionModel.status == EditStatus.IN_REVIEW,
            ProjectModel.deleted_at.is_(None),
        )
        .order_by(desc(EditVersionModel.created_at))
    )
    rows = (await session.execute(q)).all()
    return [
        AwaitingItem(
            project_id=p.id,
            project_title=p.title,
            stage=p.stage,
            cut_id=cut.id,
            cut_version=cut.version_number,
            uploaded_at=cut.created_at,
            uploader_id=cut.uploader_id,
        )
        for cut, p in rows
    ]


# ---------- 2. stage histogram ----------


async def stage_counts(session: AsyncSession) -> list[StageCount]:
    """Count of live projects per stage. Stages with zero rows still appear
    (so the frontend can render a stable axis).
    """
    q = (
        select(ProjectModel.stage, func.count())
        .where(ProjectModel.deleted_at.is_(None))
        .group_by(ProjectModel.stage)
    )
    raw = (await session.execute(q)).all()
    counts: dict[PipelineStage, int] = {stage: int(count) for stage, count in raw}
    return [
        StageCount(stage=stage, count=counts.get(stage, 0))
        for stage in PipelineStage
    ]


# ---------- 3. stuck ----------


async def stuck(session: AsyncSession, *, days: int) -> list[StuckProject]:
    """Projects whose most-recent activity is older than `days` ago — or that
    have no activity at all (treated as idle since project creation).

    `approved_published` projects are excluded since they're done.
    """
    threshold = datetime.now(UTC) - timedelta(days=days)

    last_activity_subq = (
        select(
            ActivityModel.project_id.label("project_id"),
            func.max(ActivityModel.created_at).label("last_at"),
        )
        .where(ActivityModel.project_id.is_not(None))
        .group_by(ActivityModel.project_id)
        .subquery()
    )

    q = (
        select(
            ProjectModel,
            UserModel.name.label("owner_name"),
            last_activity_subq.c.last_at,
        )
        .join(UserModel, UserModel.id == ProjectModel.owner_id)
        .join(
            last_activity_subq,
            last_activity_subq.c.project_id == ProjectModel.id,
            isouter=True,
        )
        .where(
            ProjectModel.deleted_at.is_(None),
            ProjectModel.stage != PipelineStage.APPROVED_PUBLISHED,
        )
    )
    rows = (await session.execute(q)).all()
    now = datetime.now(UTC)

    out: list[StuckProject] = []
    for project, owner_name, last_at in rows:
        compare = last_at or project.created_at
        if compare > threshold:
            continue
        days_idle = (now - compare).days
        out.append(
            StuckProject(
                project_id=project.id,
                project_title=project.title,
                stage=project.stage,
                owner_id=project.owner_id,
                owner_name=owner_name,
                last_activity_at=last_at,
                days_idle=days_idle,
            )
        )
    out.sort(key=lambda s: s.days_idle, reverse=True)
    return out


# ---------- 4. throughput ----------


def _iso_week_start(d: datetime) -> datetime:
    """Return the Monday 00:00 UTC of the ISO week containing `d`."""
    d_utc = d.astimezone(UTC)
    monday = d_utc - timedelta(days=d_utc.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


async def throughput(session: AsyncSession, *, weeks: int = 12) -> list[ThroughputBucket]:
    """Published projects bucketed by ISO week, oldest first.

    "Published" is signalled by a `project.stage_changed` activity row whose
    metadata `to == "approved_published"`. We use the activity rather than
    the current stage because a project that re-opens for edits and re-
    publishes should count once per publish event.
    """
    since = datetime.now(UTC) - timedelta(weeks=weeks)
    q = (
        select(ActivityModel.created_at, ActivityModel.metadata_json)
        .where(
            ActivityModel.action == "project.stage_changed",
            ActivityModel.created_at >= since,
        )
    )
    rows = (await session.execute(q)).all()

    counter: dict[datetime, int] = defaultdict(int)
    for created_at, metadata in rows:
        if (metadata or {}).get("to") != PipelineStage.APPROVED_PUBLISHED.value:
            continue
        counter[_iso_week_start(created_at)] += 1

    # Fill every week in the window with 0 so the chart axis is contiguous.
    start = _iso_week_start(since)
    cursor = start
    today_week = _iso_week_start(datetime.now(UTC))
    out: list[ThroughputBucket] = []
    while cursor <= today_week:
        out.append(ThroughputBucket(week_start=cursor, count=counter.get(cursor, 0)))
        cursor = cursor + timedelta(weeks=1)
    return out


# ---------- 5. time-in-stage ----------


async def time_in_stage(session: AsyncSession) -> list[TimeInStage]:
    """Average and max duration each project spent in each stage.

    Computed by pairing every `stage_changed` activity with the previous one
    on the same project. Stages with no exits yet (i.e. the current stage of
    every live project) report `sample_size=0`.
    """
    q = (
        select(ActivityModel.project_id, ActivityModel.created_at, ActivityModel.metadata_json)
        .where(ActivityModel.action == "project.stage_changed")
        .order_by(ActivityModel.project_id, ActivityModel.created_at)
    )
    rows = (await session.execute(q)).all()

    # Group by project; pair (from→to) with timestamps to derive dwell time.
    durations: dict[PipelineStage, list[float]] = defaultdict(list)
    by_project: dict[uuid.UUID, list[tuple[datetime, dict[str, Any]]]] = defaultdict(list)
    for project_id, created_at, metadata in rows:
        if project_id is None:
            continue
        by_project[project_id].append((created_at, metadata or {}))

    for events in by_project.values():
        for i, (created_at, metadata) in enumerate(events):
            from_value = metadata.get("from")
            if from_value is None:
                continue
            try:
                from_stage = PipelineStage(from_value)
            except ValueError:
                continue
            # Dwell time is from previous transition's timestamp (or, for the
            # first one, the project's IDEA inception — proxied by the same
            # activity's actor since we don't store the project's IDEA-entry
            # timestamp). Approximate by using the previous transition.
            if i == 0:
                continue
            prev_at, _prev_meta = events[i - 1]
            delta_days = (created_at - prev_at).total_seconds() / 86400.0
            if delta_days >= 0:
                durations[from_stage].append(delta_days)

    out: list[TimeInStage] = []
    for stage in PipelineStage:
        samples = durations.get(stage, [])
        if samples:
            avg = sum(samples) / len(samples)
            mx = max(samples)
            out.append(TimeInStage(stage=stage, sample_size=len(samples), avg_days=avg, max_days=mx))
        else:
            out.append(TimeInStage(stage=stage, sample_size=0, avg_days=None, max_days=None))
    return out


__all__ = [
    "AwaitingItem",
    "StageCount",
    "StuckProject",
    "ThroughputBucket",
    "TimeInStage",
    "awaiting",
    "stage_counts",
    "stuck",
    "throughput",
    "time_in_stage",
]
