"""Google Drive integration (Phase 3 Task 3.3).

Per-user OAuth: each team member who wants to import Google Docs into a
script connects their own Google account from `/settings`. Refresh tokens
are encrypted (`app.core.crypto`) before they land in the
`connected_google_accounts` table.

Surface:
    build_oauth_url(...)           — start of the consent flow
    exchange_code(...)             — callback handler
    upsert_connection(...)         — persist (or replace) the encrypted token
    get_connection(user_id)        — fetch + decrypt for the calling user
    delete_connection(user_id)     — /settings disconnect
    export_doc_as_html(...)        — Drive API export of a Google Doc
    google_doc_id_from_input(...)  — accept either a bare ID or a Docs URL

The `state` returned by `build_oauth_url` is an HMAC-signed envelope
`{user_id, nonce, exp}` so the callback can pin the consent flow to the
user who initiated it without trusting cookies during the Google redirect.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import re
import secrets
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.crypto import decrypt_token, encrypt_token
from app.models.connected_google_account import ConnectedGoogleAccountModel

log = structlog.get_logger(__name__)

PROVIDER_DRIVE = "google_drive"
SCOPE_DRIVE_READONLY = "https://www.googleapis.com/auth/drive.readonly"
SCOPE_USERINFO_EMAIL = "https://www.googleapis.com/auth/userinfo.email"
DEFAULT_SCOPES = (SCOPE_DRIVE_READONLY, SCOPE_USERINFO_EMAIL)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
DRIVE_FILES_API = "https://www.googleapis.com/drive/v3/files"

_STATE_TTL_SECONDS = 600  # 10 min — user has to finish the Google flow within this


class DriveNotConfiguredError(RuntimeError):
    """GOOGLE_DRIVE_CLIENT_* env vars are missing."""


class InvalidOAuthStateError(Exception):
    """The `state` returned by Google did not verify."""


class GoogleApiError(Exception):
    """A non-2xx response from a Google endpoint."""

    def __init__(self, status_code: int, body: str) -> None:
        super().__init__(f"google api {status_code}: {body[:200]}")
        self.status_code = status_code
        self.body = body


class NotConnectedError(Exception):
    """The user has no active Google Drive connection."""


@dataclass(frozen=True)
class TokenExchangeResult:
    refresh_token: str
    access_token: str
    expires_in: int
    scopes: str
    google_email: str


# ---------- config helpers ----------

def _require_drive_config() -> tuple[str, str, str]:
    s = get_settings()
    if not s.google_drive_client_id or not s.google_drive_client_secret:
        raise DriveNotConfiguredError(
            "GOOGLE_DRIVE_CLIENT_ID / GOOGLE_DRIVE_CLIENT_SECRET are not set"
        )
    return s.google_drive_client_id, s.google_drive_client_secret, s.google_drive_redirect_uri


# ---------- OAuth state (HMAC-signed envelope) ----------

def _state_secret() -> bytes:
    return get_settings().jwt_secret.encode()


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    padding = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + padding)


def sign_state(user_id: uuid.UUID, *, ttl_seconds: int = _STATE_TTL_SECONDS) -> str:
    """Pack `{user_id, nonce, exp}` and HMAC-sign with the JWT secret."""
    payload = {
        "sub": str(user_id),
        "nonce": secrets.token_urlsafe(16),
        "exp": int((datetime.now(UTC) + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    body = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64url_encode(hmac.new(_state_secret(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def verify_state(state: str) -> uuid.UUID:
    """Return the user id encoded in `state` or raise `InvalidOAuthStateError`."""
    try:
        body, sig = state.split(".", 1)
    except ValueError as exc:
        raise InvalidOAuthStateError("malformed state") from exc

    expected = _b64url_encode(hmac.new(_state_secret(), body.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(expected, sig):
        raise InvalidOAuthStateError("bad signature")

    try:
        payload = json.loads(_b64url_decode(body))
        user_id = uuid.UUID(payload["sub"])
        exp = int(payload["exp"])
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        raise InvalidOAuthStateError("malformed payload") from exc

    if datetime.now(UTC).timestamp() > exp:
        raise InvalidOAuthStateError("state expired")
    return user_id


# ---------- OAuth URL build + token exchange ----------

def build_oauth_url(user_id: uuid.UUID, *, scopes: Sequence[str] = DEFAULT_SCOPES) -> str:
    """Return the Google consent screen URL the frontend should redirect to."""
    client_id, _, redirect_uri = _require_drive_config()
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),
        # `access_type=offline` + `prompt=consent` are what get us a refresh
        # token on every connect (Google omits it on silent re-grants).
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": sign_state(user_id),
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_code(code: str) -> TokenExchangeResult:
    """Trade an authorization code for refresh + access tokens + the user's email."""
    client_id, client_secret, redirect_uri = _require_drive_config()
    async with httpx.AsyncClient(timeout=15) as c:
        token_resp = await c.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code != 200:
            raise GoogleApiError(token_resp.status_code, token_resp.text)
        token_body = token_resp.json()
        refresh_token = token_body.get("refresh_token")
        access_token = token_body.get("access_token")
        if not refresh_token or not access_token:
            # Google omits refresh_token when the user has already granted
            # consent and we didn't force `prompt=consent`. We do force it,
            # but surface a useful error if a future caller changes that.
            raise GoogleApiError(
                token_resp.status_code,
                "token response missing refresh_token; revoke and reconnect",
            )

        userinfo_resp = await c.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if userinfo_resp.status_code != 200:
            raise GoogleApiError(userinfo_resp.status_code, userinfo_resp.text)
        userinfo = userinfo_resp.json()
        google_email = userinfo.get("email")
        if not google_email:
            raise GoogleApiError(200, "userinfo missing email")

    return TokenExchangeResult(
        refresh_token=refresh_token,
        access_token=access_token,
        expires_in=int(token_body.get("expires_in", 3600)),
        scopes=token_body.get("scope", " ".join(DEFAULT_SCOPES)),
        google_email=google_email,
    )


async def refresh_access_token(refresh_token: str) -> str:
    """Use a stored refresh token to mint a fresh access token."""
    client_id, client_secret, _ = _require_drive_config()
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
    if r.status_code != 200:
        raise GoogleApiError(r.status_code, r.text)
    body = r.json()
    access_token = body.get("access_token")
    if not access_token:
        raise GoogleApiError(200, "refresh response missing access_token")
    return str(access_token)


# ---------- connection persistence ----------

async def upsert_connection(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    google_email: str,
    refresh_token: str,
    scopes: str,
    provider: str = PROVIDER_DRIVE,
) -> ConnectedGoogleAccountModel:
    """Insert or replace the (user, provider) row with an encrypted token."""
    existing_q = await session.execute(
        select(ConnectedGoogleAccountModel).where(
            ConnectedGoogleAccountModel.user_id == user_id,
            ConnectedGoogleAccountModel.provider == provider,
        )
    )
    row = existing_q.scalar_one_or_none()
    encrypted = encrypt_token(refresh_token)
    now = datetime.now(UTC)
    if row is None:
        row = ConnectedGoogleAccountModel(
            user_id=user_id,
            provider=provider,
            google_email=google_email,
            encrypted_refresh_token=encrypted,
            scopes=scopes,
            connected_at=now,
        )
        session.add(row)
        await session.flush()
        log.info(
            "drive_connection_created",
            user_id=str(user_id),
            google_email=google_email,
        )
        return row

    row.google_email = google_email
    row.encrypted_refresh_token = encrypted
    row.scopes = scopes
    row.connected_at = now
    log.info(
        "drive_connection_refreshed",
        user_id=str(user_id),
        google_email=google_email,
    )
    return row


async def get_connection(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    provider: str = PROVIDER_DRIVE,
) -> ConnectedGoogleAccountModel | None:
    result = await session.execute(
        select(ConnectedGoogleAccountModel).where(
            ConnectedGoogleAccountModel.user_id == user_id,
            ConnectedGoogleAccountModel.provider == provider,
        )
    )
    return result.scalar_one_or_none()


async def delete_connection(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    provider: str = PROVIDER_DRIVE,
) -> bool:
    row = await get_connection(session, user_id=user_id, provider=provider)
    if row is None:
        return False
    await session.delete(row)
    return True


async def access_token_for_user(
    session: AsyncSession, *, user_id: uuid.UUID
) -> str:
    """Decrypt the user's refresh token and mint a fresh access token."""
    row = await get_connection(session, user_id=user_id)
    if row is None:
        raise NotConnectedError(f"user {user_id} has no Drive connection")
    refresh_token = decrypt_token(row.encrypted_refresh_token)
    return await refresh_access_token(refresh_token)


# ---------- Drive API: export a Google Doc as HTML ----------

_GOOGLE_DOC_URL_RE = re.compile(r"/document/d/([a-zA-Z0-9_-]+)")


def google_doc_id_from_input(value: str) -> str:
    """Accept either a bare document ID or a `docs.google.com` URL.

    Raises `ValueError` if the input is neither.
    """
    v = value.strip()
    m = _GOOGLE_DOC_URL_RE.search(v)
    if m:
        return m.group(1)
    # Bare IDs are alphanumeric + `_-`.
    if re.fullmatch(r"[a-zA-Z0-9_-]{20,}", v):
        return v
    raise ValueError("not a Google Doc ID or URL")


async def list_documents(
    *,
    access_token: str,
    query: str | None = None,
    page_size: int = 50,
) -> list[dict[str, Any]]:
    """List the user's Google Docs from Drive, newest-modified first.

    Filters to `application/vnd.google-apps.document` so we don't surface
    spreadsheets, slides, or random PDFs in the picker. When `query` is
    given we apply a substring `name contains` filter — Drive's full-text
    search is more expensive and rate-limited, so the cheaper title filter
    is what the picker needs.

    Returns a list of `{id, name, modified_time, web_view_link}` dicts.
    """
    q_parts = ["mimeType='application/vnd.google-apps.document'", "trashed=false"]
    if query:
        # Drive's `q` parser requires escaped single quotes inside literals.
        safe = query.replace("'", "\\'")
        q_parts.append(f"name contains '{safe}'")
    params = {
        "q": " and ".join(q_parts),
        "pageSize": str(min(max(page_size, 1), 100)),
        "fields": "files(id,name,modifiedTime,webViewLink)",
        "orderBy": "modifiedTime desc",
        "spaces": "drive",
    }
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(
            DRIVE_FILES_API,
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if r.status_code != 200:
        raise GoogleApiError(r.status_code, r.text)
    payload = r.json()
    return list(payload.get("files", []))


async def export_doc_as_html(*, document_id: str, access_token: str) -> str:
    """Use Drive's `export` endpoint to download a Google Doc as HTML."""
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(
            f"{DRIVE_FILES_API}/{document_id}/export",
            params={"mimeType": "text/html"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if r.status_code != 200:
        raise GoogleApiError(r.status_code, r.text)
    return r.text


async def html_to_markdown(html: str) -> str:
    """Convert a Google-Docs HTML export into Markdown.

    `markdownify` is synchronous and CPU-bound; offload to a thread so we
    don't block the event loop on a multi-MB doc.
    """
    from markdownify import markdownify  # local import — keep startup cheap

    return await asyncio.to_thread(
        markdownify, html, heading_style="ATX", strip=["span", "div"]
    )


def project_drive_payload(folder_id: str, folder_url: str | None) -> dict[str, Any]:
    """Helper for the /drive/attach response."""
    return {"drive_folder_id": folder_id, "drive_folder_url": folder_url}


__all__ = [
    "DEFAULT_SCOPES",
    "PROVIDER_DRIVE",
    "DriveNotConfiguredError",
    "GoogleApiError",
    "InvalidOAuthStateError",
    "NotConnectedError",
    "TokenExchangeResult",
    "access_token_for_user",
    "build_oauth_url",
    "delete_connection",
    "exchange_code",
    "export_doc_as_html",
    "get_connection",
    "google_doc_id_from_input",
    "html_to_markdown",
    "project_drive_payload",
    "refresh_access_token",
    "sign_state",
    "upsert_connection",
    "verify_state",
]
