"""Phase 2 Task 2.1 — Location / Casting / Shoot endpoints.

End-to-end coverage of the auto-advance chain that's the whole point of
this module:

    LOCATION_SCOUTING  (first location)
       ↓ confirm location
    CASTING
       ↓ all cast confirmed + at least one location confirmed
    SHOOT_SCHEDULED
       ↓ wrap shoot
    SHOOT_DONE

Per-test fresh users with unique emails (same pattern as test_projects).
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
        email=f"pytest-{role.value}-{suffix}@example.com",
        name=f"Test {role.value}",
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
async def ceo(db_session: AsyncSession) -> AsyncIterator[UserModel]:
    yield await _make_user(db_session, Role.CEO)


async def _create_project(client: AsyncClient, user: UserModel) -> dict[str, Any]:
    resp = await client.post(
        "/projects",
        json={"title": "Phase-2 test", "category": Category.PROPERTY_TOUR.value},
        headers=_bearer(user),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------- Locations ----------

async def test_create_location_pushes_project_to_scouting(
    app_client: AsyncClient, ceo: UserModel
) -> None:
    project = await _create_project(app_client, ceo)
    resp = await app_client.post(
        f"/projects/{project['id']}/locations",
        json={"address": "Herengracht 123, Amsterdam"},
        headers=_bearer(ceo),
    )
    assert resp.status_code == 201, resp.text
    loc = resp.json()
    assert loc["address"] == "Herengracht 123, Amsterdam"
    assert loc["confirmed"] is False
    assert loc["photos"] == []

    # Project must now sit in LOCATION_SCOUTING.
    refreshed = await app_client.get(f"/projects/{project['id']}", headers=_bearer(ceo))
    assert refreshed.status_code == 200
    assert refreshed.json()["stage"] == PipelineStage.LOCATION_SCOUTING.value


async def test_confirm_location_advances_to_casting(
    app_client: AsyncClient, ceo: UserModel
) -> None:
    project = await _create_project(app_client, ceo)
    resp = await app_client.post(
        f"/projects/{project['id']}/locations",
        json={"address": "Keizersgracht 1, Amsterdam"},
        headers=_bearer(ceo),
    )
    loc_id = resp.json()["id"]

    resp = await app_client.post(f"/locations/{loc_id}/confirm", headers=_bearer(ceo))
    assert resp.status_code == 200
    assert resp.json()["confirmed"] is True

    refreshed = await app_client.get(f"/projects/{project['id']}", headers=_bearer(ceo))
    assert refreshed.json()["stage"] == PipelineStage.CASTING.value


# ---------- Cast ----------

async def test_full_chain_to_shoot_scheduled(
    app_client: AsyncClient, ceo: UserModel
) -> None:
    project = await _create_project(app_client, ceo)
    # Confirmed location.
    loc = (
        await app_client.post(
            f"/projects/{project['id']}/locations",
            json={"address": "Prinsengracht 7"},
            headers=_bearer(ceo),
        )
    ).json()
    await app_client.post(f"/locations/{loc['id']}/confirm", headers=_bearer(ceo))

    # One cast member, unconfirmed → still CASTING.
    cast_resp = await app_client.post(
        f"/projects/{project['id']}/cast",
        json={"name": "Sara Yılmaz", "role_description": "Host"},
        headers=_bearer(ceo),
    )
    assert cast_resp.status_code == 201, cast_resp.text
    cast_id = cast_resp.json()["id"]
    assert (
        (await app_client.get(f"/projects/{project['id']}", headers=_bearer(ceo)))
        .json()["stage"]
        == PipelineStage.CASTING.value
    )

    # Confirm — now all cast (n=1) confirmed AND a location confirmed.
    confirmed = await app_client.post(f"/cast/{cast_id}/confirm", headers=_bearer(ceo))
    assert confirmed.status_code == 200
    assert (
        (await app_client.get(f"/projects/{project['id']}", headers=_bearer(ceo)))
        .json()["stage"]
        == PipelineStage.SHOOT_SCHEDULED.value
    )


# ---------- Shoot ----------

async def test_shoot_state_machine_and_wrap_advances_project(
    app_client: AsyncClient, ceo: UserModel
) -> None:
    project = await _create_project(app_client, ceo)
    # Fast-track project to SHOOT_SCHEDULED via /stage so we don't rebuild
    # the whole chain — `can_user_move_to_stage` allows CEO anywhere except
    # APPROVED_PUBLISHED.
    move = await app_client.post(
        f"/projects/{project['id']}/stage",
        json={"stage": PipelineStage.SHOOT_SCHEDULED.value},
        headers=_bearer(ceo),
    )
    assert move.status_code == 200

    resp = await app_client.post(
        f"/projects/{project['id']}/shoots",
        json={"scheduled_at": "2026-06-01T10:00:00+00:00", "gear_checklist": {"cam_a": True}},
        headers=_bearer(ceo),
    )
    assert resp.status_code == 201, resp.text
    shoot = resp.json()
    assert shoot["status"] == "scheduled"
    assert shoot["gear_checklist"] == {"cam_a": True}
    shoot_id = shoot["id"]

    # Illegal jump (scheduled → wrapped) should 409.
    bad = await app_client.post(f"/shoots/{shoot_id}/wrap", headers=_bearer(ceo))
    assert bad.status_code == 409

    started = await app_client.post(f"/shoots/{shoot_id}/start", headers=_bearer(ceo))
    assert started.status_code == 200
    assert started.json()["status"] == "in_progress"
    assert started.json()["started_at"] is not None

    wrapped = await app_client.post(f"/shoots/{shoot_id}/wrap", headers=_bearer(ceo))
    assert wrapped.status_code == 200
    assert wrapped.json()["status"] == "wrapped"
    assert wrapped.json()["wrapped_at"] is not None

    refreshed = await app_client.get(f"/projects/{project['id']}", headers=_bearer(ceo))
    assert refreshed.json()["stage"] == PipelineStage.SHOOT_DONE.value
