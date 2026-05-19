"""Script versioning + comments + lock/unlock tests (Phase 1 Task 1.6)."""

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
        email=f"scripttest-{role.value}-{suffix}@example.com",
        name=f"ScriptTest {role.value}",
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
    yield {
        Role.CEO: await _make_user(db_session, Role.CEO),
        Role.ASSISTANT_DIRECTOR: await _make_user(db_session, Role.ASSISTANT_DIRECTOR),
        Role.JUNIOR_DIRECTOR: await _make_user(db_session, Role.JUNIOR_DIRECTOR),
        Role.EDITOR: await _make_user(db_session, Role.EDITOR),
    }


async def _make_project(client: AsyncClient, owner: UserModel) -> str:
    body: dict[str, Any] = {"title": "script-test", "category": Category.PROPERTY_TOUR.value}
    resp = await client.post("/projects", json=body, headers=_bearer(owner))
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ---------- versions ----------

async def test_create_first_version_advances_stage(
    app_client: AsyncClient, roles: dict[Role, UserModel]
) -> None:
    director = roles[Role.ASSISTANT_DIRECTOR]
    project_id = await _make_project(app_client, director)

    resp = await app_client.post(
        f"/projects/{project_id}/scripts/versions",
        json={"body_markdown": "# Draft 1"},
        headers=_bearer(director),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["version_number"] == 1

    # Project should now be in SCRIPT_DRAFTING
    proj = await app_client.get(f"/projects/{project_id}", headers=_bearer(director))
    assert proj.json()["stage"] == PipelineStage.SCRIPT_DRAFTING.value


async def test_subsequent_versions_increment(
    app_client: AsyncClient, roles: dict[Role, UserModel]
) -> None:
    director = roles[Role.ASSISTANT_DIRECTOR]
    project_id = await _make_project(app_client, director)

    for i in range(1, 4):
        resp = await app_client.post(
            f"/projects/{project_id}/scripts/versions",
            json={"body_markdown": f"# V{i}"},
            headers=_bearer(director),
        )
        assert resp.status_code == 201
        assert resp.json()["version_number"] == i

    listing = await app_client.get(
        f"/projects/{project_id}/scripts/versions", headers=_bearer(director)
    )
    assert [v["version_number"] for v in listing.json()] == [1, 2, 3]


async def test_editor_cannot_create_version_for_other_owner(
    app_client: AsyncClient, roles: dict[Role, UserModel]
) -> None:
    director = roles[Role.ASSISTANT_DIRECTOR]
    project_id = await _make_project(app_client, director)
    resp = await app_client.post(
        f"/projects/{project_id}/scripts/versions",
        json={"body_markdown": "# attempt"},
        headers=_bearer(roles[Role.EDITOR]),
    )
    assert resp.status_code == 403


# ---------- submit / lock / unlock ----------

async def test_submit_then_lock_then_unlock(
    app_client: AsyncClient, roles: dict[Role, UserModel]
) -> None:
    director = roles[Role.ASSISTANT_DIRECTOR]
    project_id = await _make_project(app_client, director)
    await app_client.post(
        f"/projects/{project_id}/scripts/versions",
        json={"body_markdown": "# v1"},
        headers=_bearer(director),
    )

    # Submit (drafting → review)
    submit = await app_client.post(
        f"/projects/{project_id}/scripts/submit", headers=_bearer(director)
    )
    assert submit.status_code == 200
    proj = await app_client.get(f"/projects/{project_id}", headers=_bearer(director))
    assert proj.json()["stage"] == PipelineStage.SCRIPT_REVIEW.value

    # Lock (Jr Dir can lock IF owner; director can always)
    lock = await app_client.post(
        f"/projects/{project_id}/scripts/lock", headers=_bearer(director)
    )
    assert lock.status_code == 200
    proj = await app_client.get(f"/projects/{project_id}", headers=_bearer(director))
    assert proj.json()["stage"] == PipelineStage.SCRIPT_LOCKED.value

    # Unlock — Jr Dir is NOT allowed, only CEO/Asst
    jr_unlock = await app_client.post(
        f"/projects/{project_id}/scripts/unlock", headers=_bearer(roles[Role.JUNIOR_DIRECTOR])
    )
    assert jr_unlock.status_code == 403

    unlock = await app_client.post(
        f"/projects/{project_id}/scripts/unlock", headers=_bearer(director)
    )
    assert unlock.status_code == 200
    proj = await app_client.get(f"/projects/{project_id}", headers=_bearer(director))
    assert proj.json()["stage"] == PipelineStage.SCRIPT_REVIEW.value


async def test_cannot_add_version_when_locked(
    app_client: AsyncClient, roles: dict[Role, UserModel]
) -> None:
    director = roles[Role.ASSISTANT_DIRECTOR]
    project_id = await _make_project(app_client, director)
    await app_client.post(
        f"/projects/{project_id}/scripts/versions",
        json={"body_markdown": "# v1"},
        headers=_bearer(director),
    )
    await app_client.post(f"/projects/{project_id}/scripts/lock", headers=_bearer(director))

    resp = await app_client.post(
        f"/projects/{project_id}/scripts/versions",
        json={"body_markdown": "# attempt"},
        headers=_bearer(director),
    )
    assert resp.status_code == 409
    assert "locked" in resp.json()["detail"].lower()


async def test_editor_cannot_lock(
    app_client: AsyncClient, roles: dict[Role, UserModel]
) -> None:
    director = roles[Role.ASSISTANT_DIRECTOR]
    project_id = await _make_project(app_client, director)
    await app_client.post(
        f"/projects/{project_id}/scripts/versions",
        json={"body_markdown": "# v1"},
        headers=_bearer(director),
    )
    await app_client.post(f"/projects/{project_id}/scripts/submit", headers=_bearer(director))

    resp = await app_client.post(
        f"/projects/{project_id}/scripts/lock", headers=_bearer(roles[Role.EDITOR])
    )
    assert resp.status_code == 403


# ---------- comments ----------

async def test_add_comment_then_resolve_then_reopen(
    app_client: AsyncClient, roles: dict[Role, UserModel]
) -> None:
    director = roles[Role.ASSISTANT_DIRECTOR]
    project_id = await _make_project(app_client, director)
    vers = await app_client.post(
        f"/projects/{project_id}/scripts/versions",
        json={"body_markdown": "# v1"},
        headers=_bearer(director),
    )
    version_id = vers.json()["id"]

    added = await app_client.post(
        f"/scripts/versions/{version_id}/comments",
        json={"body": "Fix paragraph 2", "paragraph_anchor": "p2"},
        headers=_bearer(director),
    )
    assert added.status_code == 201, added.text
    comment_id = added.json()["id"]
    assert added.json()["resolved_at"] is None

    listing = await app_client.get(
        f"/scripts/versions/{version_id}/comments", headers=_bearer(director)
    )
    assert len(listing.json()) == 1

    resolved = await app_client.post(
        f"/scripts/comments/{comment_id}/resolve", headers=_bearer(director)
    )
    assert resolved.status_code == 200
    assert resolved.json()["resolved_at"] is not None

    reopened = await app_client.post(
        f"/scripts/comments/{comment_id}/reopen", headers=_bearer(director)
    )
    assert reopened.status_code == 200
    assert reopened.json()["resolved_at"] is None
