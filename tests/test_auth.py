"""Auth tests — slim surface after the NextAuth pivot.

Login, password change, invitation, and password reset all live in the
Next.js layer now. The backend exposes only `GET /auth/me` for server-
rendered Next.js pages that want to re-validate the session against the
source of truth. These tests exercise that endpoint.
"""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import issue_access_token
from app.models.enums import Role
from app.models.user import UserModel


async def _make_user(session: AsyncSession, role: Role) -> UserModel:
    user = UserModel(
        email=f"pytest-{uuid.uuid4().hex[:8]}@example.com",
        name=f"Pytest {role.value}",
        role=role,
        locale="nl",
    )
    session.add(user)
    await session.commit()
    return user


def _bearer(user: UserModel) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {issue_access_token(user_id=user.id, email=user.email, role=user.role)}"
    }


async def test_me_without_token_returns_401(app_client: AsyncClient) -> None:
    resp = await app_client.get("/auth/me")
    assert resp.status_code == 401


async def test_me_with_garbage_token_returns_401(app_client: AsyncClient) -> None:
    resp = await app_client.get("/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401


async def test_me_returns_user_for_valid_token(
    app_client: AsyncClient, db_session: AsyncSession
) -> None:
    user = await _make_user(db_session, Role.EDITOR)
    resp = await app_client.get("/auth/me", headers=_bearer(user))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["email"] == user.email
    assert body["role"] == "editor"


async def test_me_401s_softdeleted_users(
    app_client: AsyncClient, db_session: AsyncSession
) -> None:
    from datetime import UTC, datetime

    user = await _make_user(db_session, Role.EDITOR)
    user.deleted_at = datetime.now(UTC)
    await db_session.commit()
    resp = await app_client.get("/auth/me", headers=_bearer(user))
    assert resp.status_code == 401
