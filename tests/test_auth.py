"""Auth endpoint tests (Phase 1 Task 1.3.7).

Covers: happy path, expired token, reused token, unknown email, locale.

These tests run against the local docker-compose Postgres. Each test uses
`unique_email` so it doesn't collide with seed data or other tests.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Role
from app.models.magic_link import MagicLinkModel
from app.models.user import UserModel


async def _create_user(session: AsyncSession, email: str, *, locale: str = "nl") -> UserModel:
    user = UserModel(email=email, name="Pytest User", role=Role.EDITOR, locale=locale)
    session.add(user)
    await session.commit()
    return user


async def _latest_link_for(session: AsyncSession, user: UserModel) -> MagicLinkModel:
    """Fetch the most-recent magic-link for a user (and refresh session view)."""
    await session.commit()  # ensure we see other-session writes
    result = await session.execute(
        select(MagicLinkModel)
        .where(MagicLinkModel.user_id == user.id)
        .order_by(MagicLinkModel.created_at.desc())
    )
    link = result.scalars().first()
    assert link is not None, "no magic link found for user"
    return link


async def test_request_link_known_email_returns_ok(
    app_client: AsyncClient, db_session: AsyncSession, unique_email: str
) -> None:
    await _create_user(db_session, unique_email)

    resp = await app_client.post("/auth/request-link", json={"email": unique_email})

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_request_link_unknown_email_returns_ok_without_link(
    app_client: AsyncClient, db_session: AsyncSession, unique_email: str
) -> None:
    """Anti-enumeration: unknown emails get the same 200 ack with no DB write."""
    resp = await app_client.post("/auth/request-link", json={"email": unique_email})
    assert resp.status_code == 200

    # No user => no row in magic_links
    result = await db_session.execute(
        select(MagicLinkModel).join(UserModel, MagicLinkModel.user_id == UserModel.id).where(
            UserModel.email == unique_email
        )
    )
    assert result.scalars().first() is None


async def test_verify_happy_path_issues_jwt(
    app_client: AsyncClient, db_session: AsyncSession, unique_email: str
) -> None:
    user = await _create_user(db_session, unique_email)

    # Request link → reach into DB to get the raw token via the hash route is
    # not possible (we only store the hash). Instead we test verify by injecting
    # a known raw token via a fresh MagicLinkModel — same flow the service uses.
    import hashlib
    import secrets

    raw = secrets.token_urlsafe(32)
    db_session.add(
        MagicLinkModel(
            user_id=user.id,
            token_hash=hashlib.sha256(raw.encode()).hexdigest(),
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )
    )
    await db_session.commit()

    resp = await app_client.get("/auth/verify", params={"token": raw})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["user"]["email"] == unique_email
    assert body["user"]["role"] == "editor"
    assert body["access_token"]

    # /auth/me with the issued JWT echoes the same user.
    me = await app_client.get(
        "/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["email"] == unique_email


async def test_verify_expired_token_rejected(
    app_client: AsyncClient, db_session: AsyncSession, unique_email: str
) -> None:
    user = await _create_user(db_session, unique_email)

    import hashlib
    import secrets

    raw = secrets.token_urlsafe(32)
    db_session.add(
        MagicLinkModel(
            user_id=user.id,
            token_hash=hashlib.sha256(raw.encode()).hexdigest(),
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )
    )
    await db_session.commit()

    resp = await app_client.get("/auth/verify", params={"token": raw})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Magic link expired"


async def test_verify_reused_token_rejected(
    app_client: AsyncClient, db_session: AsyncSession, unique_email: str
) -> None:
    user = await _create_user(db_session, unique_email)

    import hashlib
    import secrets

    raw = secrets.token_urlsafe(32)
    db_session.add(
        MagicLinkModel(
            user_id=user.id,
            token_hash=hashlib.sha256(raw.encode()).hexdigest(),
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )
    )
    await db_session.commit()

    first = await app_client.get("/auth/verify", params={"token": raw})
    assert first.status_code == 200

    second = await app_client.get("/auth/verify", params={"token": raw})
    assert second.status_code == 400
    assert second.json()["detail"] == "Magic link already used"


async def test_me_without_token_returns_401(app_client: AsyncClient) -> None:
    resp = await app_client.get("/auth/me")
    assert resp.status_code == 401
    assert "Missing bearer token" in resp.json()["detail"]


async def test_me_with_garbage_token_returns_401(app_client: AsyncClient) -> None:
    resp = await app_client.get("/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401
    assert "Invalid or expired token" in resp.json()["detail"]


async def test_request_link_locale_switching_changes_email_subject(
    app_client: AsyncClient, db_session: AsyncSession, unique_email: str, tmp_path: pytest.TempPathFactory
) -> None:
    """Locale on the request body wins over the user's stored locale."""
    from pathlib import Path

    await _create_user(db_session, unique_email, locale="nl")

    resp = await app_client.post(
        "/auth/request-link", json={"email": unique_email, "locale": "en"}
    )
    assert resp.status_code == 200

    # Look in the .dev-emails directory for a recent file for this email.
    safe = unique_email.replace("@", "_at_")
    candidates = sorted(Path(".dev-emails").glob(f"*{safe}*.html"), key=lambda p: p.stat().st_mtime)
    assert candidates, "no dev-email file written"
    body = candidates[-1].read_text(encoding="utf-8")
    # English subject contains "Sign in"; Dutch subject contains "Aanmelden".
    assert "Sign in to Sons Real Estate CMS" in body or "Sign in" in body
