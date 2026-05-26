"""Dashboard aggregations (Phase 3 Task 3.2).

Pure read-side queries over `projects`, `edit_versions`, and `activities`. No
mutations, no permissions — routes gate access. All times are computed in UTC.

Five summaries:
    awaiting()         — final cuts waiting on approval
    stage_counts()     — histogram across the department's stages
    stuck(threshold)   — projects with no activity for ≥ N days
    throughput(weeks)  — projects published per ISO week
    time_in_stage()    — average + max days spent per stage

Stages are looked up in code via `app.services.stage_registry` (the
`department_stages` table was dropped 2026-05-26). Each project carries a
`stage_key` string and the department carries the `template_key` we use to
resolve stage metadata.
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
from app.models.department import DepartmentModel
from app.models.edit import EditVersionModel
from app.models.enums import EditStatus
from app.models.project import ProjectModel
from app.models.user import UserModel
from app.services import stage_registry

log = structlog.get_logger(__name__)


# ---------- DTOs ----------


@dataclass(frozen=True)
class AwaitingItem:
    project_id: uuid.UUID
    project_title: str
    stage: str
    cut_id: uuid.UUID
    cut_version: int
    uploaded_at: datetime
    uploader_id: uuid.UUID | None


@dataclass(frozen=True)
class StageCount:
    stage: str
    count: int


@dataclass(frozen=True)
class StuckProject:
    project_id: uuid.UUID
    project_title: str
    stage: str
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
    stage: str
    sample_size: int
    avg_days: float | None
    max_days: float | None


# ---------- helpers ----------


async def _template_stages_for(
    session: AsyncSession, *, department_id: uuid.UUID
) -> list[dict[str, Any]]:
    """Resolve the department's template stages from the in-code registry."""
    department = await session.get(DepartmentModel, department_id)
    if department is None:
        return []
    return stage_registry.get_stages(department.template_key)


def _terminal_keys_from(stages: list[dict[str, Any]]) -> set[str]:
    return {s["key"] for s in stages if s.get("is_terminal")}


# ---------- 1. awaiting ----------


async def awaiting(
    session: AsyncSession, *, department_id: uuid.UUID
) -> list[AwaitingItem]:
    """Cuts whose status is still IN_REVIEW — the CEO's approval queue."""
    q = (
        select(EditVersionModel, ProjectModel)
        .join(ProjectModel, ProjectModel.id == EditVersionModel.project_id)
        .where(
            EditVersionModel.status == EditStatus.IN_REVIEW,
            ProjectModel.deleted_at.is_(None),
            ProjectModel.department_id == department_id,
        )
        .order_by(desc(EditVersionModel.created_at))
    )
    rows = (await session.execute(q)).all()
    return [
        AwaitingItem(
            project_id=p.id,
            project_title=p.title,
            stage=p.stage_key,
            cut_id=cut.id,
            cut_version=cut.version_number,
            uploaded_at=cut.created_at,
            uploader_id=cut.uploader_id,
        )
        for cut, p in rows
    ]


# ---------- 2. stage histogram ----------


async def stage_counts(
    session: AsyncSession, *, department_id: uuid.UUID
) -> list[StageCount]:
    """Count of live projects per stage. Stages with zero rows still appear."""
    stages = await _template_stages_for(session, department_id=department_id)
    if not stages:
        return []

    q = (
        select(ProjectModel.stage_key, func.count(ProjectModel.id))
        .where(
            ProjectModel.department_id == department_id,
            ProjectModel.deleted_at.is_(None),
        )
        .group_by(ProjectModel.stage_key)
    )
    raw = (await session.execute(q)).all()
    counts_by_key = {key: int(count) for key, count in raw}
    # Iterate registry order so the chart axis is deterministic and stages
    # without rows still appear.
    return [StageCount(stage=s["key"], count=counts_by_key.get(s["key"], 0)) for s in stages]


# ---------- 3. stuck ----------


async def stuck(
    session: AsyncSession, *, department_id: uuid.UUID, days: int
) -> list[StuckProject]:
    """Projects whose most-recent activity is older than `days` ago."""
    threshold = datetime.now(UTC) - timedelta(days=days)
    stages = await _template_stages_for(session, department_id=department_id)
    terminal_keys = _terminal_keys_from(stages)

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
            ProjectModel.department_id == department_id,
        )
    )
    rows = (await session.execute(q)).all()
    now = datetime.now(UTC)

    out: list[StuckProject] = []
    for project, owner_name, last_at in rows:
        if project.stage_key in terminal_keys:
            continue
        compare = last_at or project.created_at
        if compare > threshold:
            continue
        days_idle = (now - compare).days
        out.append(
            StuckProject(
                project_id=project.id,
                project_title=project.title,
                stage=project.stage_key,
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


async def throughput(
    session: AsyncSession, *, department_id: uuid.UUID, weeks: int = 12
) -> list[ThroughputBucket]:
    """Published projects bucketed by ISO week, oldest first.

    "Published" is signalled by a `project.stage_changed` activity row whose
    `metadata.to` matches any terminal stage key in the department. We use
    activity rather than current stage so a project that re-opens for edits
    and re-publishes counts once per publish event.
    """
    since = datetime.now(UTC) - timedelta(weeks=weeks)
    stages = await _template_stages_for(session, department_id=department_id)
    terminal_keys = _terminal_keys_from(stages)

    q = (
        select(ActivityModel.created_at, ActivityModel.metadata_json)
        .join(ProjectModel, ProjectModel.id == ActivityModel.project_id)
        .where(
            ActivityModel.action == "project.stage_changed",
            ActivityModel.created_at >= since,
            ProjectModel.department_id == department_id,
        )
    )
    rows = (await session.execute(q)).all()

    counter: dict[datetime, int] = defaultdict(int)
    for created_at, metadata in rows:
        to_key = (metadata or {}).get("to")
        if to_key not in terminal_keys:
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


async def time_in_stage(
    session: AsyncSession, *, department_id: uuid.UUID
) -> list[TimeInStage]:
    """Average and max duration projects spent in each stage."""
    stages = await _template_stages_for(session, department_id=department_id)
    stage_keys = [s["key"] for s in stages]
    known = set(stage_keys)

    q = (
        select(ActivityModel.project_id, ActivityModel.created_at, ActivityModel.metadata_json)
        .join(ProjectModel, ProjectModel.id == ActivityModel.project_id)
        .where(
            ActivityModel.action == "project.stage_changed",
            ProjectModel.department_id == department_id,
        )
        .order_by(ActivityModel.project_id, ActivityModel.created_at)
    )
    rows = (await session.execute(q)).all()

    durations: dict[str, list[float]] = defaultdict(list)
    by_project: dict[uuid.UUID, list[tuple[datetime, dict[str, object]]]] = defaultdict(list)
    for project_id, created_at, metadata in rows:
        if project_id is None:
            continue
        by_project[project_id].append((created_at, metadata or {}))

    for events in by_project.values():
        for i, (created_at, metadata) in enumerate(events):
            from_value = metadata.get("from")
            if not isinstance(from_value, str) or from_value not in known:
                continue
            if i == 0:
                continue
            prev_at, _prev_meta = events[i - 1]
            delta_days = (created_at - prev_at).total_seconds() / 86400.0
            if delta_days >= 0:
                durations[from_value].append(delta_days)

    out: list[TimeInStage] = []
    for key in stage_keys:
        samples = durations.get(key, [])
        if samples:
            avg = sum(samples) / len(samples)
            mx = max(samples)
            out.append(TimeInStage(stage=key, sample_size=len(samples), avg_days=avg, max_days=mx))
        else:
            out.append(TimeInStage(stage=key, sample_size=0, avg_days=None, max_days=None))
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
