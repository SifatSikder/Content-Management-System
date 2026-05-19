"""Activity feed tests (Phase 1 Task 1.8.4).

The activity log is written by every mutating endpoint via
`activity_service.record`; here we drive a few real mutations and then verify
the feed reads them back in order with pagination.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import issue_access_token
from app.models.enums import Category, PipelineStage, Role
from app.models.user import UserModel


async def _make_user(session: AsyncSession, role: Role) -> UserModel:
    suffix = uuid.uuid4().hex[:8]
    user = UserModel(
        email=f"acttest-{role.value}-{suffix}@example.com",
        name=f"ActTest {role.value}",
        role=role,
        locale="nl",
    )
    session.add(user)
    await session.commit()
    return user


def _bearer(user: UserModel) -> dict[str, str]:
    token = issue_access_token(user_id=user.id, email=user.email, role=user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def director(db_session: AsyncSession) -> AsyncIterator[UserModel]:
    yield await _make_user(db_session, Role.ASSISTANT_DIRECTOR)


async def test_activity_logged_for_project_lifecycle(
    app_client: AsyncClient, director: UserModel
) -> None:
    body: dict[str, Any] = {"title": "act-test", "category": Category.PROPERTY_TOUR.value}
    create = await app_client.post("/projects", json=body, headers=_bearer(director))
    project_id = create.json()["id"]

    # Patch + stage move → 2 more activity rows
    await app_client.patch(
        f"/projects/{project_id}",
        json={"title": "act-test (updated)"},
        headers=_bearer(director),
    )
    await app_client.post(
        f"/projects/{project_id}/stage",
        json={"stage": PipelineStage.SCRIPT_DRAFTING.value},
        headers=_bearer(director),
    )

    feed = await app_client.get(
        f"/projects/{project_id}/activity?limit=50", headers=_bearer(director)
    )
    assert feed.status_code == 200, feed.text
    items = feed.json()["items"]
    actions = [item["action"] for item in items]
    # Most-recent first
    assert "project.stage_changed" in actions
    assert "project.updated" in actions
    assert "project.created" in actions
    # Verify ordering: stage_changed was last action so it should appear first.
    assert actions.index("project.stage_changed") < actions.index("project.created")


async def test_activity_pagination(app_client: AsyncClient, director: UserModel) -> None:
    body: dict[str, Any] = {"title": "page-act", "category": Category.PROPERTY_TOUR.value}
    create = await app_client.post("/projects", json=body, headers=_bearer(director))
    project_id = create.json()["id"]

    # Generate a handful of activity rows.
    for i in range(5):
        await app_client.patch(
            f"/projects/{project_id}",
            json={"description": f"v{i}"},
            headers=_bearer(director),
        )

    first = await app_client.get(
        f"/projects/{project_id}/activity?limit=2", headers=_bearer(director)
    )
    assert first.status_code == 200
    page1 = first.json()
    assert len(page1["items"]) == 2
    assert page1["next_cursor"] is not None

    second = await app_client.get(
        f"/projects/{project_id}/activity?limit=2&cursor={page1['next_cursor']}",
        headers=_bearer(director),
    )
    assert second.status_code == 200
    page2 = second.json()
    page1_ids = {it["id"] for it in page1["items"]}
    page2_ids = {it["id"] for it in page2["items"]}
    assert page1_ids.isdisjoint(page2_ids)
