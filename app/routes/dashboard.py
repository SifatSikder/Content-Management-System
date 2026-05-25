"""Dashboard endpoints (Phase 3 Task 3.2 → Phase B).

All five readouts are visible to every authenticated user — the dashboard
is shared situational awareness, not gated by role. Crew users see the same
numbers as the CEO; they just don't have stage-move buttons elsewhere.

Phase B: aggregations are scoped to a single `department_id` (passed as a
query parameter). The frontend resolves this from the user's current
department before calling.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, SessionDep
from app.schemas.dashboard import (
    AwaitingItemPublic,
    StageCountPublic,
    StuckProjectPublic,
    ThroughputBucketPublic,
    TimeInStagePublic,
)
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


DeptId = Annotated[uuid.UUID, Query(alias="department_id", description="Department to scope the dashboard to.")]


@router.get(
    "/awaiting",
    response_model=list[AwaitingItemPublic],
    summary="Cuts currently in review — the approval queue",
)
async def get_awaiting(
    session: SessionDep,
    _user: CurrentUser,
    department_id: DeptId,
) -> list[AwaitingItemPublic]:
    rows = await dashboard_service.awaiting(session, department_id=department_id)
    return [AwaitingItemPublic.model_validate(r) for r in rows]


@router.get(
    "/stages",
    response_model=list[StageCountPublic],
    summary="Histogram of live projects per pipeline stage",
)
async def get_stages(
    session: SessionDep,
    _user: CurrentUser,
    department_id: DeptId,
) -> list[StageCountPublic]:
    rows = await dashboard_service.stage_counts(session, department_id=department_id)
    return [StageCountPublic.model_validate(r) for r in rows]


@router.get(
    "/stuck",
    response_model=list[StuckProjectPublic],
    summary="Projects with no activity for at least `days` days",
)
async def get_stuck(
    session: SessionDep,
    _user: CurrentUser,
    department_id: DeptId,
    days: Annotated[int, Query(ge=1, le=365)] = 5,
) -> list[StuckProjectPublic]:
    rows = await dashboard_service.stuck(session, department_id=department_id, days=days)
    return [StuckProjectPublic.model_validate(r) for r in rows]


@router.get(
    "/throughput",
    response_model=list[ThroughputBucketPublic],
    summary="Projects published per ISO week (oldest first)",
)
async def get_throughput(
    session: SessionDep,
    _user: CurrentUser,
    department_id: DeptId,
    weeks: Annotated[int, Query(ge=1, le=52)] = 12,
) -> list[ThroughputBucketPublic]:
    rows = await dashboard_service.throughput(session, department_id=department_id, weeks=weeks)
    return [ThroughputBucketPublic.model_validate(r) for r in rows]


@router.get(
    "/time-in-stage",
    response_model=list[TimeInStagePublic],
    summary="Average + max days per stage across all projects",
)
async def get_time_in_stage(
    session: SessionDep,
    _user: CurrentUser,
    department_id: DeptId,
) -> list[TimeInStagePublic]:
    rows = await dashboard_service.time_in_stage(session, department_id=department_id)
    return [TimeInStagePublic.model_validate(r) for r in rows]


__all__ = ["router"]
