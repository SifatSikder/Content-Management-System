"""Phase 3 Task 3.3 — Google Drive integration tests.

Covers token encryption, OAuth state signing, the consent-flow callback,
the /projects/{id}/drive/attach surface, and /scripts/import-gdoc. All
real Google calls are intercepted with `respx`.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
import pytest_asyncio
import respx
from cryptography.fernet import Fernet
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import issue_access_token
from app.config import get_settings
from app.core.crypto import (
    TokenDecryptionError,
    TokenEncryptionNotConfiguredError,
    decrypt_token,
    encrypt_token,
)
from app.models.connected_google_account import ConnectedGoogleAccountModel
from app.models.enums import Category, Role
from app.models.user import UserModel
from app.services import drive_service
from app.services.drive_service import (
    InvalidOAuthStateError,
    google_doc_id_from_input,
    sign_state,
    verify_state,
)

# ---------- fixtures ----------


@pytest.fixture(autouse=True)
def drive_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Populate the Drive + encryption settings on the cached Settings instance."""
    settings = get_settings()
    monkeypatch.setattr(settings, "token_encryption_key", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "google_drive_client_id", "test-client-id")
    monkeypatch.setattr(settings, "google_drive_client_secret", "test-client-secret")
    monkeypatch.setattr(
        settings,
        "google_drive_redirect_uri",
        "http://localhost:8000/auth/google/drive/callback",
    )
    monkeypatch.setattr(
        settings,
        "google_drive_post_auth_redirect",
        "http://localhost:3000/settings",
    )
    yield


async def _make_user(session: AsyncSession, role: Role) -> UserModel:
    suffix = uuid.uuid4().hex[:8]
    user = UserModel(
        email=f"drivetest-{role.value}-{suffix}@example.com",
        name=f"DriveTest {role.value}",
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


@pytest_asyncio.fixture
async def crew(db_session: AsyncSession) -> AsyncIterator[UserModel]:
    yield await _make_user(db_session, Role.CREW)


async def _make_project(client: AsyncClient, owner: UserModel) -> str:
    body: dict[str, Any] = {
        "title": "drive-test",
        "category": Category.PROPERTY_TOUR.value,
    }
    resp = await client.post("/projects", json=body, headers=_bearer(owner))
    assert resp.status_code == 201, resp.text
    return str(resp.json()["id"])


# ---------- crypto unit tests ----------


def test_crypto_roundtrip() -> None:
    plaintext = "1//refresh-token-from-google"
    ct = encrypt_token(plaintext)
    assert ct != plaintext
    assert decrypt_token(ct) == plaintext


def test_crypto_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "token_encryption_key", None)
    with pytest.raises(TokenEncryptionNotConfiguredError):
        encrypt_token("x")


def test_crypto_rejects_wrong_key(monkeypatch: pytest.MonkeyPatch) -> None:
    ct = encrypt_token("secret")
    monkeypatch.setattr(get_settings(), "token_encryption_key", Fernet.generate_key().decode())
    with pytest.raises(TokenDecryptionError):
        decrypt_token(ct)


# ---------- OAuth state unit tests ----------


def test_state_sign_verify_roundtrip() -> None:
    uid = uuid.uuid4()
    state = sign_state(uid)
    assert verify_state(state) == uid


def test_state_rejects_tampered_signature() -> None:
    state = sign_state(uuid.uuid4())
    body, sig = state.split(".")
    bad = f"{body}.{'A' * len(sig)}"
    with pytest.raises(InvalidOAuthStateError):
        verify_state(bad)


def test_state_rejects_expired() -> None:
    expired = sign_state(uuid.uuid4(), ttl_seconds=-1)
    time.sleep(0.01)
    with pytest.raises(InvalidOAuthStateError):
        verify_state(expired)


# ---------- google_doc_id_from_input ----------


@pytest.mark.parametrize(
    "value,expected",
    [
        ("1A2B3C4D5E6F7G8H9I0JabcdEFGH", "1A2B3C4D5E6F7G8H9I0JabcdEFGH"),
        (
            "https://docs.google.com/document/d/1A2B3C4D5E6F7G8H9I0JabcdEFGH/edit",
            "1A2B3C4D5E6F7G8H9I0JabcdEFGH",
        ),
        (
            "https://docs.google.com/document/d/1A2B3C4D5E6F7G8H9I0JabcdEFGH/edit?usp=sharing",
            "1A2B3C4D5E6F7G8H9I0JabcdEFGH",
        ),
    ],
)
def test_doc_id_parser_accepts(value: str, expected: str) -> None:
    assert google_doc_id_from_input(value) == expected


@pytest.mark.parametrize("value", ["", "nope", "short-id"])
def test_doc_id_parser_rejects(value: str) -> None:
    with pytest.raises(ValueError):
        google_doc_id_from_input(value)


# ---------- /auth/google/drive/start ----------


async def test_start_returns_consent_url(
    app_client: AsyncClient, ceo: UserModel
) -> None:
    resp = await app_client.post("/auth/google/drive/start", headers=_bearer(ceo))
    assert resp.status_code == 200, resp.text
    url = resp.json()["url"]
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "client_id=test-client-id" in url
    assert "scope=https" in url
    assert "state=" in url


async def test_start_503_when_drive_unconfigured(
    app_client: AsyncClient, ceo: UserModel, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "google_drive_client_id", None)
    resp = await app_client.post("/auth/google/drive/start", headers=_bearer(ceo))
    assert resp.status_code == 503


# ---------- /auth/google/drive/callback ----------


async def test_callback_invalid_state_400(app_client: AsyncClient) -> None:
    resp = await app_client.get(
        "/auth/google/drive/callback",
        params={"code": "x", "state": "garbage"},
    )
    assert resp.status_code == 400


@respx.mock
async def test_callback_success_persists_connection(
    app_client: AsyncClient, ceo: UserModel, db_session: AsyncSession
) -> None:
    respx.post("https://oauth2.googleapis.com/token").mock(
        return_value=Response(
            200,
            json={
                "access_token": "ya29.fake-access",
                "refresh_token": "1//fake-refresh",
                "expires_in": 3600,
                "scope": "https://www.googleapis.com/auth/drive.readonly",
                "token_type": "Bearer",
            },
        )
    )
    respx.get("https://openidconnect.googleapis.com/v1/userinfo").mock(
        return_value=Response(200, json={"email": "ceo@gmail.com"})
    )

    state = sign_state(ceo.id)
    resp = await app_client.get(
        "/auth/google/drive/callback",
        params={"code": "auth-code-123", "state": state},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 307)
    assert "drive=connected" in resp.headers["location"]

    row = (
        await db_session.execute(
            select(ConnectedGoogleAccountModel).where(
                ConnectedGoogleAccountModel.user_id == ceo.id
            )
        )
    ).scalar_one()
    assert row.google_email == "ceo@gmail.com"
    assert decrypt_token(row.encrypted_refresh_token) == "1//fake-refresh"


# ---------- /auth/google/drive/me + disconnect ----------


async def test_me_then_disconnect(
    app_client: AsyncClient, ceo: UserModel, db_session: AsyncSession
) -> None:
    # Seed a connection directly.
    await drive_service.upsert_connection(
        db_session,
        user_id=ceo.id,
        google_email="ceo@gmail.com",
        refresh_token="1//direct-seed",
        scopes=drive_service.SCOPE_DRIVE_READONLY,
    )
    await db_session.commit()

    me = await app_client.get("/auth/google/drive/me", headers=_bearer(ceo))
    assert me.status_code == 200
    assert me.json()["google_email"] == "ceo@gmail.com"

    disc = await app_client.delete(
        "/auth/google/drive/disconnect", headers=_bearer(ceo)
    )
    assert disc.status_code == 204

    me2 = await app_client.get("/auth/google/drive/me", headers=_bearer(ceo))
    assert me2.status_code == 404


# ---------- /projects/{id}/drive/attach ----------


async def test_attach_drive_folder_owner_ok(
    app_client: AsyncClient, ceo: UserModel
) -> None:
    project_id = await _make_project(app_client, ceo)
    resp = await app_client.post(
        f"/projects/{project_id}/drive/attach",
        json={
            "folder_id": "0AABBCCDDEEFF",
            "folder_url": "https://drive.google.com/drive/folders/0AABBCCDDEEFF",
        },
        headers=_bearer(ceo),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["drive_folder_id"] == "0AABBCCDDEEFF"


async def test_attach_drive_folder_crew_forbidden(
    app_client: AsyncClient, ceo: UserModel, crew: UserModel
) -> None:
    project_id = await _make_project(app_client, ceo)
    resp = await app_client.post(
        f"/projects/{project_id}/drive/attach",
        json={"folder_id": "0AABBCCDDEEFF"},
        headers=_bearer(crew),
    )
    assert resp.status_code == 403


async def test_detach_drive_folder(
    app_client: AsyncClient, ceo: UserModel
) -> None:
    project_id = await _make_project(app_client, ceo)
    await app_client.post(
        f"/projects/{project_id}/drive/attach",
        json={"folder_id": "0AABBCCDDEEFF"},
        headers=_bearer(ceo),
    )
    detach = await app_client.delete(
        f"/projects/{project_id}/drive/attach", headers=_bearer(ceo)
    )
    assert detach.status_code == 200
    assert detach.json()["drive_folder_id"] is None


# ---------- /projects/{id}/scripts/import-gdoc ----------


async def test_import_gdoc_412_when_not_connected(
    app_client: AsyncClient, ceo: UserModel
) -> None:
    project_id = await _make_project(app_client, ceo)
    resp = await app_client.post(
        f"/projects/{project_id}/scripts/import-gdoc",
        json={"document": "https://docs.google.com/document/d/1A2B3C4D5E6F7G8H9I0JabcdEFGH/edit"},
        headers=_bearer(ceo),
    )
    assert resp.status_code == 412


@respx.mock
async def test_import_gdoc_happy_path(
    app_client: AsyncClient,
    ceo: UserModel,
    db_session: AsyncSession,
) -> None:
    await drive_service.upsert_connection(
        db_session,
        user_id=ceo.id,
        google_email="ceo@gmail.com",
        refresh_token="1//direct-seed",
        scopes=drive_service.SCOPE_DRIVE_READONLY,
    )
    await db_session.commit()

    respx.post("https://oauth2.googleapis.com/token").mock(
        return_value=Response(
            200,
            json={
                "access_token": "ya29.refreshed",
                "expires_in": 3600,
                "scope": "https://www.googleapis.com/auth/drive.readonly",
            },
        )
    )
    doc_id = "1A2B3C4D5E6F7G8H9I0JabcdEFGH"
    respx.get(f"https://www.googleapis.com/drive/v3/files/{doc_id}/export").mock(
        return_value=Response(
            200,
            text="<html><body><h1>Imported Title</h1><p>Body text here.</p></body></html>",
        )
    )

    project_id = await _make_project(app_client, ceo)
    resp = await app_client.post(
        f"/projects/{project_id}/scripts/import-gdoc",
        json={"document": doc_id},
        headers=_bearer(ceo),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["version_number"] == 1
    assert "Imported Title" in body["body_markdown"]
