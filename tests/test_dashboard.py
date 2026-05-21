"""Dashboard endpoint tests (Phase 3 Task 3.2)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import issue_access_token
from app.models.activity import ActivityModel
from app.models.enums import Category, EditStatus, PipelineStage, Role
from app.models.project import ProjectModel
from app.models.user import UserModel


async def _make_user(session: AsyncSession, role: Role) -> UserModel:
    suffix = uuid.uuid4().hex[:8]
    user = UserModel(
        email=f"dashtest-{role.value}-{suffix}@example.com",
        name=f"DashTest {role.value}",
        role=role,
        locale="nl",
    )
    session.add(user)
    await session.commit()
    return user


def _bearer(user: UserModel) -> dict[str, str]:
    token = issue_access_token(user_id=user.id, email=user.email, role=user.role)
    return {"Authorization": f"Bearer {token}"}


async def _make_project(client: AsyncClient, owner: UserModel, title: str = "dash-test") -> str:
    body: dict[str, Any] = {"title": title, "category": Category.PROPERTY_TOUR.value}
    resp = await client.post("/projects", json=body, headers=_bearer(owner))
    assert resp.status_code == 201, resp.text
    return str(resp.json()["id"])


@pytest_asyncio.fixture
async def ceo(db_session: AsyncSession) -> AsyncIterator[UserModel]:
    yield await _make_user(db_session, Role.CEO)


# ---------- /dashboard/stages ----------


async def test_stages_returns_all_11_buckets(
    app_client: AsyncClient, ceo: UserModel
) -> None:
    resp = await app_client.get("/dashboard/stages", headers=_bearer(ceo))
    assert resp.status_code == 200
    data = resp.json()
    stages_seen = {row["stage"] for row in data}
    # Every PipelineStage value must be represented, even if count is 0.
    for stage in PipelineStage:
        assert stage.value in stages_seen
    assert all(row["count"] >= 0 for row in data)


async def test_stages_counts_a_new_project(
    app_client: AsyncClient, ceo: UserModel
) -> None:
    before = {row["stage"]: row["count"] for row in (
        await app_client.get("/dashboard/stages", headers=_bearer(ceo))
    ).json()}
    await _make_project(app_client, ceo, "stage-count-1")
    after = {row["stage"]: row["count"] for row in (
        await app_client.get("/dashboard/stages", headers=_bearer(ceo))
    ).json()}
    assert after["idea"] == before["idea"] + 1


# ---------- /dashboard/awaiting ----------


async def test_awaiting_returns_in_review_cuts(
    app_client: AsyncClient,
    ceo: UserModel,
    db_session: AsyncSession,
) -> None:
    """Seed an EditVersion in IN_REVIEW and confirm it appears in the queue."""
    from app.models.edit import EditVersionModel

    project_id = await _make_project(app_client, ceo, "awaiting-test")
    cut = EditVersionModel(
        project_id=uuid.UUID(project_id),
        version_number=1,
        uploader_id=ceo.id,
        gcs_bucket="sre-video-dev",
        gcs_object_name=f"projects/{project_id}/edits/v1.mp4",
        content_type="video/mp4",
        size_bytes=1024,
        status=EditStatus.IN_REVIEW,
        resolved_comments=[],
    )
    db_session.add(cut)
    await db_session.commit()

    resp = await app_client.get("/dashboard/awaiting", headers=_bearer(ceo))
    assert resp.status_code == 200
    matches = [r for r in resp.json() if r["project_id"] == project_id]
    assert len(matches) == 1
    assert matches[0]["cut_version"] == 1


# ---------- /dashboard/stuck ----------


async def test_stuck_surfaces_old_project(
    app_client: AsyncClient,
    ceo: UserModel,
    db_session: AsyncSession,
) -> None:
    """A project whose created_at is 10 days ago + no activity → appears in stuck."""
    project_id = await _make_project(app_client, ceo, "stuck-test")
    old = datetime.now(UTC) - timedelta(days=10)
    # Backdate the project so it counts as stuck. Also wipe any activity rows
    # the create-project flow inserted, so created_at is the only signal.
    await db_session.execute(
        update(ProjectModel)
        .where(ProjectModel.id == uuid.UUID(project_id))
        .values(created_at=old)
    )
    await db_session.execute(
        ActivityModel.__table__.delete().where(
            ActivityModel.project_id == uuid.UUID(project_id)
        )
    )
    await db_session.commit()

    resp = await app_client.get(
        "/dashboard/stuck", params={"days": 5}, headers=_bearer(ceo)
    )
    assert resp.status_code == 200
    matches = [r for r in resp.json() if r["project_id"] == project_id]
    assert len(matches) == 1
    assert matches[0]["days_idle"] >= 5


async def test_stuck_excludes_recent_project(
    app_client: AsyncClient, ceo: UserModel
) -> None:
    project_id = await _make_project(app_client, ceo, "stuck-not")
    resp = await app_client.get(
        "/dashboard/stuck", params={"days": 5}, headers=_bearer(ceo)
    )
    assert resp.status_code == 200
    assert all(r["project_id"] != project_id for r in resp.json())


# ---------- /dashboard/throughput ----------


async def test_throughput_fills_full_window(
    app_client: AsyncClient, ceo: UserModel
) -> None:
    resp = await app_client.get(
        "/dashboard/throughput", params={"weeks": 4}, headers=_bearer(ceo)
    )
    assert resp.status_code == 200
    data = resp.json()
    # 4 weeks back + the current week = 5 buckets minimum (depending on day-of-week).
    assert len(data) >= 4
    assert all("week_start" in row and "count" in row for row in data)


async def test_throughput_counts_publish_event(
    app_client: AsyncClient,
    ceo: UserModel,
    db_session: AsyncSession,
) -> None:
    """Seed a project.stage_changed activity → approved_published; confirm bucket increments."""
    project_id = await _make_project(app_client, ceo, "throughput-test")
    activity = ActivityModel(
        project_id=uuid.UUID(project_id),
        actor_id=ceo.id,
        action="project.stage_changed",
        metadata_json={"from": "final_review", "to": "approved_published"},
    )
    db_session.add(activity)
    await db_session.commit()

    resp = await app_client.get(
        "/dashboard/throughput", params={"weeks": 4}, headers=_bearer(ceo)
    )
    total = sum(row["count"] for row in resp.json())
    assert total >= 1


# ---------- /dashboard/time-in-stage ----------


async def test_time_in_stage_returns_all_stages(
    app_client: AsyncClient, ceo: UserModel
) -> None:
    resp = await app_client.get("/dashboard/time-in-stage", headers=_bearer(ceo))
    assert resp.status_code == 200
    data = resp.json()
    stages_seen = {row["stage"] for row in data}
    for stage in PipelineStage:
        assert stage.value in stages_seen
    # sample_size=0 stages should have null avg/max.
    for row in data:
        if row["sample_size"] == 0:
            assert row["avg_days"] is None
            assert row["max_days"] is None
        else:
            assert row["avg_days"] is not None


# ---------- auth ----------


async def test_dashboard_requires_auth(app_client: AsyncClient) -> None:
    resp = await app_client.get("/dashboard/awaiting")
    assert resp.status_code == 401
