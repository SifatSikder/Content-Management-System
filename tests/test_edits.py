"""Edit upload + review tests (Phase 1 Task 1.7).

These tests use fake-gcs-server (started via `make up`). The frontend would
PUT chunks to the upload session URL — for tests we bypass that step and
write the blob via the GCS SDK directly, so we still exercise the backend's
finalise / playback / approve paths end-to-end.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import issue_access_token
from app.models.enums import Category, EditStatus, PipelineStage, Role
from app.models.user import UserModel
from app.services import storage_service


async def _make_user(session: AsyncSession, role: Role) -> UserModel:
    suffix = uuid.uuid4().hex[:8]
    user = UserModel(
        email=f"edittest-{role.value}-{suffix}@example.com",
        name=f"EditTest {role.value}",
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
    body: dict[str, Any] = {"title": "edit-test", "category": Category.PROPERTY_TOUR.value}
    resp = await client.post("/projects", json=body, headers=_bearer(owner))
    assert resp.status_code == 201
    return resp.json()["id"]


async def _upload_bytes(bucket: str, object_name: str, content: bytes, content_type: str) -> None:
    """Bypass the resumable session and write bytes via the SDK directly."""

    def _sync() -> None:
        from google.cloud import storage as gcs  # noqa: F401  # ensure import

        # Reuse the cached client + bucket setup from the service.
        bucket_ref = storage_service._ensure_bucket(bucket)
        blob = bucket_ref.blob(object_name)  # type: ignore[attr-defined]
        blob.upload_from_string(content, content_type=content_type)

    await asyncio.to_thread(_sync)


# ---------- init upload ----------

async def test_init_upload_rejects_bad_content_type(
    app_client: AsyncClient, roles: dict[Role, UserModel]
) -> None:
    director = roles[Role.ASSISTANT_DIRECTOR]
    project_id = await _make_project(app_client, director)
    resp = await app_client.post(
        f"/projects/{project_id}/edits/init-upload",
        json={"content_type": "image/png", "size_bytes": 100},
        headers=_bearer(director),
    )
    assert resp.status_code == 400


async def test_init_upload_rejects_oversize(
    app_client: AsyncClient, roles: dict[Role, UserModel]
) -> None:
    director = roles[Role.ASSISTANT_DIRECTOR]
    project_id = await _make_project(app_client, director)
    too_big = 3 * 1024 * 1024 * 1024  # 3 GB > 2 GB cap
    resp = await app_client.post(
        f"/projects/{project_id}/edits/init-upload",
        json={"content_type": "video/mp4", "size_bytes": too_big},
        headers=_bearer(director),
    )
    assert resp.status_code == 422  # pydantic field validation


async def test_init_upload_returns_session_url(
    app_client: AsyncClient, roles: dict[Role, UserModel]
) -> None:
    director = roles[Role.ASSISTANT_DIRECTOR]
    project_id = await _make_project(app_client, director)
    resp = await app_client.post(
        f"/projects/{project_id}/edits/init-upload",
        json={"content_type": "video/mp4", "size_bytes": 1024},
        headers=_bearer(director),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["upload_session_url"].startswith("http")
    assert body["gcs_object_name"].startswith(f"projects/{project_id}/edits/")
    assert body["gcs_object_name"].endswith(".mp4")


# ---------- finalise ----------

async def test_finalise_fails_when_blob_missing(
    app_client: AsyncClient, roles: dict[Role, UserModel]
) -> None:
    director = roles[Role.ASSISTANT_DIRECTOR]
    project_id = await _make_project(app_client, director)
    resp = await app_client.post(
        f"/projects/{project_id}/edits",
        json={
            "gcs_bucket": "sre-video-dev",
            "gcs_object_name": f"projects/{project_id}/edits/does-not-exist.mp4",
            "content_type": "video/mp4",
            "size_bytes": 100,
        },
        headers=_bearer(director),
    )
    assert resp.status_code == 400
    assert "not found" in resp.json()["detail"].lower()


async def test_full_upload_finalise_flow_advances_to_editing(
    app_client: AsyncClient, roles: dict[Role, UserModel]
) -> None:
    director = roles[Role.ASSISTANT_DIRECTOR]
    project_id = await _make_project(app_client, director)

    init = await app_client.post(
        f"/projects/{project_id}/edits/init-upload",
        json={"content_type": "video/mp4", "size_bytes": 16},
        headers=_bearer(director),
    )
    bucket = init.json()["gcs_bucket"]
    object_name = init.json()["gcs_object_name"]

    await _upload_bytes(bucket, object_name, b"\x00" * 16, "video/mp4")

    finalise = await app_client.post(
        f"/projects/{project_id}/edits",
        json={
            "gcs_bucket": bucket,
            "gcs_object_name": object_name,
            "content_type": "video/mp4",
            "size_bytes": 16,
            "notes": "First cut",
        },
        headers=_bearer(director),
    )
    assert finalise.status_code == 201, finalise.text
    edit = finalise.json()
    assert edit["version_number"] == 1
    assert edit["status"] == EditStatus.IN_REVIEW.value

    proj = await app_client.get(f"/projects/{project_id}", headers=_bearer(director))
    assert proj.json()["stage"] == PipelineStage.EDITING.value


# ---------- playback URL ----------

async def test_playback_url_returns_emulator_link(
    app_client: AsyncClient, roles: dict[Role, UserModel]
) -> None:
    director = roles[Role.ASSISTANT_DIRECTOR]
    project_id = await _make_project(app_client, director)

    init = await app_client.post(
        f"/projects/{project_id}/edits/init-upload",
        json={"content_type": "video/mp4", "size_bytes": 8},
        headers=_bearer(director),
    )
    bucket = init.json()["gcs_bucket"]
    object_name = init.json()["gcs_object_name"]
    await _upload_bytes(bucket, object_name, b"abcdefgh", "video/mp4")

    finalise = await app_client.post(
        f"/projects/{project_id}/edits",
        json={
            "gcs_bucket": bucket,
            "gcs_object_name": object_name,
            "content_type": "video/mp4",
            "size_bytes": 8,
        },
        headers=_bearer(director),
    )
    edit_id = finalise.json()["id"]

    playback = await app_client.get(
        f"/edits/{edit_id}/playback-url", headers=_bearer(director)
    )
    assert playback.status_code == 200
    body = playback.json()
    assert body["url"].startswith("http")
    assert body["expires_in_seconds"] == 15 * 60


# ---------- approve / request-changes ----------

async def test_request_changes_then_approve_flow(
    app_client: AsyncClient, roles: dict[Role, UserModel]
) -> None:
    director = roles[Role.ASSISTANT_DIRECTOR]
    project_id = await _make_project(app_client, director)

    init = await app_client.post(
        f"/projects/{project_id}/edits/init-upload",
        json={"content_type": "video/mp4", "size_bytes": 8},
        headers=_bearer(director),
    )
    bucket = init.json()["gcs_bucket"]
    object_name = init.json()["gcs_object_name"]
    await _upload_bytes(bucket, object_name, b"01234567", "video/mp4")
    finalise = await app_client.post(
        f"/projects/{project_id}/edits",
        json={
            "gcs_bucket": bucket,
            "gcs_object_name": object_name,
            "content_type": "video/mp4",
            "size_bytes": 8,
        },
        headers=_bearer(director),
    )
    edit_id = finalise.json()["id"]

    # Editor can't approve.
    fb = await app_client.post(
        f"/edits/{edit_id}/approve", headers=_bearer(roles[Role.EDITOR])
    )
    assert fb.status_code == 403

    # Asst Dir requests changes.
    rc = await app_client.post(
        f"/edits/{edit_id}/request-changes",
        json={"notes": "Tighten pacing 0:00-0:30."},
        headers=_bearer(director),
    )
    assert rc.status_code == 200
    assert rc.json()["status"] == EditStatus.CHANGES_REQUESTED.value

    # Cannot approve a cut after request_changes? Actually we allow re-approve.
    # CEO approves → project moves to APPROVED_PUBLISHED.
    ceo_ok = await app_client.post(
        f"/edits/{edit_id}/approve", headers=_bearer(roles[Role.CEO])
    )
    assert ceo_ok.status_code == 200
    assert ceo_ok.json()["status"] == EditStatus.APPROVED.value
    proj = await app_client.get(f"/projects/{project_id}", headers=_bearer(director))
    assert proj.json()["stage"] == PipelineStage.APPROVED_PUBLISHED.value
