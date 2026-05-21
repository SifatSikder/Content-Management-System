"""Notification-prefs endpoints + push gate (Phase 3 Task 3.5)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import issue_access_token
from app.models.enums import Role
from app.models.user import UserModel
from app.services import notification_prefs_service, push_service


async def _make_user(session: AsyncSession, role: Role = Role.CEO) -> UserModel:
    suffix = uuid.uuid4().hex[:8]
    user = UserModel(
        email=f"prefs-{role.value}-{suffix}@example.com",
        name=f"Prefs {role.value}",
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
async def user(db_session: AsyncSession) -> AsyncIterator[UserModel]:
    yield await _make_user(db_session)


async def test_get_creates_defaults(app_client: AsyncClient, user: UserModel) -> None:
    resp = await app_client.get("/me/notification-prefs", headers=_bearer(user))
    assert resp.status_code == 200
    data = resp.json()
    # Opt-out model: all toggles default to True.
    assert all(value is True for value in data.values())


async def test_patch_toggles_subset(app_client: AsyncClient, user: UserModel) -> None:
    resp = await app_client.patch(
        "/me/notification-prefs",
        json={"push_cut_uploaded": False, "push_cut_comment": False},
        headers=_bearer(user),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["push_cut_uploaded"] is False
    assert data["push_cut_comment"] is False
    # Untouched fields stay True.
    assert data["push_project_published"] is True

    # GET reflects the new state.
    again = await app_client.get("/me/notification-prefs", headers=_bearer(user))
    assert again.json()["push_cut_uploaded"] is False


async def test_is_event_enabled_gates_notify(
    db_session: AsyncSession, user: UserModel
) -> None:
    # Mute cut_uploaded for this user.
    await notification_prefs_service.update_prefs(
        db_session, user_id=user.id, patch={"cut_uploaded": False}
    )
    await db_session.commit()

    enabled = await notification_prefs_service.is_event_enabled(
        db_session, user_id=user.id, event_key="cut_uploaded"
    )
    assert enabled is False

    # notify_user with the muted event_key returns 0 without touching Redis.
    sent = await push_service.notify_user(
        db_session,
        user_id=user.id,
        payload={"title": "muted", "body": "should not send"},
        event_key="cut_uploaded",
    )
    assert sent == 0


async def test_unknown_event_key_defaults_open(
    db_session: AsyncSession, user: UserModel
) -> None:
    """Belt-and-braces: a typo'd event_key should not silently mute everyone."""
    enabled = await notification_prefs_service.is_event_enabled(
        db_session, user_id=user.id, event_key="totally_made_up"
    )
    assert enabled is True
