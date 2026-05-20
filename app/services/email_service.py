"""Email service — Gmail API client (backend-side).

The Phase-1 auth flow (invitations, password resets, password-changed
notices) is fronted by the Next.js layer and sends via `googleapis` in
`frontend/src/server/email.ts`. This module is the **backend** counterpart,
exposed for Phase 3 (WhatsApp + notification fanouts) where worker jobs
running outside a Next.js request need to send mail too.

Both layers share the same `GMAIL_OAUTH_*` env vars and the same sender
mailbox. Refresh tokens are durable; access tokens are minted on demand by
the Google client library.

In dev, calls raise if Gmail env vars are unset — fails loudly rather than
silently dropping mail.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import structlog

from app.config import get_settings

if TYPE_CHECKING:
    from googleapiclient.discovery import Resource

log = structlog.get_logger(__name__)


class EmailNotConfiguredError(RuntimeError):
    """Raised when GMAIL_OAUTH_* env vars are missing."""


def _require_gmail_config() -> tuple[str, str, str, str]:
    s = get_settings()
    missing = [
        name
        for name, value in {
            "GMAIL_OAUTH_CLIENT_ID": s.gmail_oauth_client_id,
            "GMAIL_OAUTH_CLIENT_SECRET": s.gmail_oauth_client_secret,
            "GMAIL_OAUTH_REFRESH_TOKEN": s.gmail_oauth_refresh_token,
            "GMAIL_SENDER_ADDRESS": s.gmail_sender_address,
        }.items()
        if not value
    ]
    if missing:
        raise EmailNotConfiguredError(
            f"Gmail send is not configured: missing {', '.join(missing)}. "
            "Run scripts/setup_gmail_oauth.py and store the values in .env.local."
        )
    assert s.gmail_oauth_client_id is not None
    assert s.gmail_oauth_client_secret is not None
    assert s.gmail_oauth_refresh_token is not None
    assert s.gmail_sender_address is not None
    return (
        s.gmail_oauth_client_id,
        s.gmail_oauth_client_secret,
        s.gmail_oauth_refresh_token,
        s.gmail_sender_address,
    )


def _build_gmail_client() -> Resource:
    """Lazily import googleapis to keep startup cheap."""
    client_id, client_secret, refresh_token, _sender = _require_gmail_config()
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(  # type: ignore[no-untyped-call]
        token=None,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/gmail.send"],
    )
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _build_raw_message(*, to: str, subject: str, html: str, sender: str) -> str:
    import base64
    from email.message import EmailMessage

    msg = EmailMessage()
    msg["To"] = to
    msg["From"] = sender
    msg["Subject"] = subject
    msg.set_content("This email requires an HTML-capable client.")
    msg.add_alternative(html, subtype="html")
    return base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")


async def send_html_email(*, to: str, subject: str, html: str) -> None:
    """Send an HTML email via Gmail API. Blocking call, run on a worker thread."""

    def _sync() -> None:
        _, _, _, sender = _require_gmail_config()
        client = _build_gmail_client()
        raw = _build_raw_message(to=to, subject=subject, html=html, sender=sender)
        client.users().messages().send(userId="me", body={"raw": raw}).execute()
        log.info("gmail_sent", to=to, subject=subject)

    await asyncio.to_thread(_sync)


__all__ = ["EmailNotConfiguredError", "send_html_email"]
