"""Project CRUD + permission tests (Phase 1 Tasks 1.4.6, 1.5).

End-to-end via httpx.AsyncClient against the FastAPI app. Each test creates
fresh users with unique emails and issues access tokens directly with
`issue_access_token` so we don't have to round-trip through the email service.
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


async def _make_user(session: AsyncSession, role: Role, *, name: str | None = None) -> UserModel:
    suffix = uuid.uuid4().hex[:8]
    user = UserModel(
        email=f"pytest-{role.value}-{suffix}@example.com",
        name=name or f"Test {role.value}",
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
async def roles(db_session: AsyncSession) -> AsyncIterator[dict[Role, UserModel]]:
    users = {
        Role.CEO: await _make_user(db_session, Role.CEO),
        Role.ASSISTANT_DIRECTOR: await _make_user(db_session, Role.ASSISTANT_DIRECTOR),
        Role.JUNIOR_DIRECTOR: await _make_user(db_session, Role.JUNIOR_DIRECTOR),
        Role.EDITOR: await _make_user(db_session, Role.EDITOR),
        Role.CREW: await _make_user(db_session, Role.CREW),
        Role.VIEWER: await _make_user(db_session, Role.VIEWER),
    }
    yield users


_PROJECT_BODY: dict[str, Any] = {
    "title": "Test project",
    "category": Category.PROPERTY_TOUR.value,
}


# ---------- Create ----------

async def test_create_project_unauth_is_401(app_client: AsyncClient) -> None:
    resp = await app_client.post("/projects", json=_PROJECT_BODY)
    assert resp.status_code == 401


async def test_create_project_as_director_201(
    app_client: AsyncClient, roles: dict[Role, UserModel]
) -> None:
    resp = await app_client.post(
        "/projects", json=_PROJECT_BODY, headers=_bearer(roles[Role.ASSISTANT_DIRECTOR])
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["title"] == _PROJECT_BODY["title"]
    assert body["stage"] == PipelineStage.IDEA.value
    assert body["owner_id"] == str(roles[Role.ASSISTANT_DIRECTOR].id)


async def test_create_project_as_editor_is_403(
    app_client: AsyncClient, roles: dict[Role, UserModel]
) -> None:
    resp = await app_client.post(
        "/projects", json=_PROJECT_BODY, headers=_bearer(roles[Role.EDITOR])
    )
    assert resp.status_code == 403


async def test_create_project_as_crew_is_403(
    app_client: AsyncClient, roles: dict[Role, UserModel]
) -> None:
    resp = await app_client.post(
        "/projects", json=_PROJECT_BODY, headers=_bearer(roles[Role.CREW])
    )
    assert resp.status_code == 403


# ---------- View ----------

async def test_get_project_owner_can_see(
    app_client: AsyncClient, roles: dict[Role, UserModel]
) -> None:
    director = roles[Role.JUNIOR_DIRECTOR]
    create = await app_client.post("/projects", json=_PROJECT_BODY, headers=_bearer(director))
    project_id = create.json()["id"]
    get = await app_client.get(f"/projects/{project_id}", headers=_bearer(director))
    assert get.status_code == 200


async def test_get_project_crew_assigned_only(
    app_client: AsyncClient, roles: dict[Role, UserModel]
) -> None:
    director = roles[Role.ASSISTANT_DIRECTOR]
    create = await app_client.post("/projects", json=_PROJECT_BODY, headers=_bearer(director))
    project_id = create.json()["id"]
    # Crew not assigned → 403
    forbidden = await app_client.get(f"/projects/{project_id}", headers=_bearer(roles[Role.CREW]))
    assert forbidden.status_code == 403


# ---------- Update ----------

async def test_update_project_editor_not_owner_is_403(
    app_client: AsyncClient, roles: dict[Role, UserModel]
) -> None:
    create = await app_client.post(
        "/projects", json=_PROJECT_BODY, headers=_bearer(roles[Role.ASSISTANT_DIRECTOR])
    )
    project_id = create.json()["id"]
    resp = await app_client.patch(
        f"/projects/{project_id}",
        json={"title": "new"},
        headers=_bearer(roles[Role.EDITOR]),
    )
    assert resp.status_code == 403


async def test_update_project_director_200(
    app_client: AsyncClient, roles: dict[Role, UserModel]
) -> None:
    create = await app_client.post(
        "/projects", json=_PROJECT_BODY, headers=_bearer(roles[Role.ASSISTANT_DIRECTOR])
    )
    project_id = create.json()["id"]
    resp = await app_client.patch(
        f"/projects/{project_id}",
        json={"title": "Updated title"},
        headers=_bearer(roles[Role.ASSISTANT_DIRECTOR]),
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated title"


# ---------- Stage move ----------

async def test_move_stage_director_owned_200(
    app_client: AsyncClient, roles: dict[Role, UserModel]
) -> None:
    director = roles[Role.JUNIOR_DIRECTOR]
    create = await app_client.post("/projects", json=_PROJECT_BODY, headers=_bearer(director))
    project_id = create.json()["id"]
    resp = await app_client.post(
        f"/projects/{project_id}/stage",
        json={"stage": PipelineStage.SCRIPT_DRAFTING.value},
        headers=_bearer(director),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["stage"] == PipelineStage.SCRIPT_DRAFTING.value


async def test_move_stage_jr_not_owner_is_403(
    app_client: AsyncClient, roles: dict[Role, UserModel]
) -> None:
    create = await app_client.post(
        "/projects", json=_PROJECT_BODY, headers=_bearer(roles[Role.ASSISTANT_DIRECTOR])
    )
    project_id = create.json()["id"]
    resp = await app_client.post(
        f"/projects/{project_id}/stage",
        json={"stage": PipelineStage.SCRIPT_DRAFTING.value},
        headers=_bearer(roles[Role.JUNIOR_DIRECTOR]),
    )
    assert resp.status_code == 403


async def test_move_to_published_only_ceo(
    app_client: AsyncClient, roles: dict[Role, UserModel]
) -> None:
    asst = roles[Role.ASSISTANT_DIRECTOR]
    create = await app_client.post("/projects", json=_PROJECT_BODY, headers=_bearer(asst))
    project_id = create.json()["id"]

    asst_attempt = await app_client.post(
        f"/projects/{project_id}/stage",
        json={"stage": PipelineStage.APPROVED_PUBLISHED.value},
        headers=_bearer(asst),
    )
    assert asst_attempt.status_code == 403

    ceo_attempt = await app_client.post(
        f"/projects/{project_id}/stage",
        json={"stage": PipelineStage.APPROVED_PUBLISHED.value},
        headers=_bearer(roles[Role.CEO]),
    )
    assert ceo_attempt.status_code == 200
    assert ceo_attempt.json()["stage"] == PipelineStage.APPROVED_PUBLISHED.value


# ---------- Soft-delete + restore ----------

async def test_soft_delete_then_restore_roundtrip(
    app_client: AsyncClient, roles: dict[Role, UserModel]
) -> None:
    ceo = roles[Role.CEO]
    create = await app_client.post("/projects", json=_PROJECT_BODY, headers=_bearer(ceo))
    project_id = create.json()["id"]

    delete = await app_client.delete(f"/projects/{project_id}", headers=_bearer(ceo))
    assert delete.status_code == 204

    # GET on deleted project should 404
    gone = await app_client.get(f"/projects/{project_id}", headers=_bearer(ceo))
    assert gone.status_code == 404

    # Restore
    restore = await app_client.post(f"/projects/{project_id}/restore", headers=_bearer(ceo))
    assert restore.status_code == 200
    assert restore.json()["deleted_at"] is None

    # And it's visible again
    again = await app_client.get(f"/projects/{project_id}", headers=_bearer(ceo))
    assert again.status_code == 200


# ---------- Listing + pagination ----------

async def test_list_projects_pagination_cursor(
    app_client: AsyncClient, roles: dict[Role, UserModel]
) -> None:
    ceo = roles[Role.CEO]
    # Create 3 fresh projects (independent of seed data).
    for i in range(3):
        body = {**_PROJECT_BODY, "title": f"page-test-{uuid.uuid4().hex[:6]}-{i}"}
        await app_client.post("/projects", json=body, headers=_bearer(ceo))

    first = await app_client.get("/projects?limit=2", headers=_bearer(ceo))
    assert first.status_code == 200
    page1 = first.json()
    assert len(page1["items"]) == 2
    assert page1["next_cursor"] is not None

    second = await app_client.get(
        f"/projects?limit=2&cursor={page1['next_cursor']}", headers=_bearer(ceo)
    )
    assert second.status_code == 200
    page2 = second.json()
    assert len(page2["items"]) >= 1
    page1_ids = {item["id"] for item in page1["items"]}
    page2_ids = {item["id"] for item in page2["items"]}
    assert page1_ids.isdisjoint(page2_ids), "pagination overlapped"


async def test_list_projects_filter_mine(
    app_client: AsyncClient, roles: dict[Role, UserModel]
) -> None:
    me = roles[Role.JUNIOR_DIRECTOR]
    other = roles[Role.ASSISTANT_DIRECTOR]
    mine_title = f"mine-{uuid.uuid4().hex[:6]}"
    other_title = f"theirs-{uuid.uuid4().hex[:6]}"
    await app_client.post(
        "/projects", json={**_PROJECT_BODY, "title": mine_title}, headers=_bearer(me)
    )
    await app_client.post(
        "/projects", json={**_PROJECT_BODY, "title": other_title}, headers=_bearer(other)
    )

    resp = await app_client.get("/projects?filter=mine&limit=50", headers=_bearer(me))
    assert resp.status_code == 200
    titles = {item["title"] for item in resp.json()["items"]}
    assert mine_title in titles
    assert other_title not in titles
