"""Auth service — magic-link request + verify.

`request_magic_link` mints a token, persists its SHA-256 hash (never the raw
token), and sends an email with a link to the frontend `/auth/callback`. The
raw token is only ever in transit and in the user's email inbox.

`verify_magic_link` looks up the hash, validates expiry + single-use, marks
consumed, and returns the user — the route then issues a JWT.

Anti-enumeration: `request_magic_link` returns the same result whether or not
the email matches an existing user.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.magic_link import MagicLinkModel
from app.models.user import UserModel
from app.services.email_service import send_magic_link

log = structlog.get_logger(__name__)


class MagicLinkExpiredError(Exception):
    """Magic-link token is past its `expires_at`."""


class MagicLinkAlreadyUsedError(Exception):
    """Magic-link token has already been consumed (single-use)."""


class MagicLinkNotFoundError(Exception):
    """Magic-link token does not match any stored hash."""


@dataclass(frozen=True)
class VerifiedUser:
    id: uuid.UUID
    email: str
    name: str
    role: str
    locale: str


def _hash_token(raw: str) -> str:
    """Return a hex SHA-256 digest of the raw token."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _build_callback_url(base_url: str, raw_token: str) -> str:
    base = base_url.rstrip("/")
    return f"{base}/auth/callback?token={raw_token}"


async def request_magic_link(
    session: AsyncSession,
    *,
    email: str,
    locale: str | None = None,
) -> None:
    """Mint a magic link for `email` (if a user exists) and send it.

    Returns nothing — the route always responds 200 to avoid leaking which
    addresses have accounts.
    """
    settings = get_settings()
    normalised_email = email.strip().lower()

    result = await session.execute(
        select(UserModel).where(
            UserModel.email == normalised_email,
            UserModel.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        log.info("magic_link_skipped_unknown_email", email=normalised_email)
        return

    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)
    expires_at = datetime.now(UTC) + timedelta(seconds=settings.magic_link_ttl_seconds)

    session.add(
        MagicLinkModel(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
    )
    await session.commit()

    link = _build_callback_url(settings.app_base_url, raw_token)
    chosen_locale = locale or user.locale or "nl"
    send_magic_link(to=user.email, locale=chosen_locale, link=link)
    log.info("magic_link_issued", user_id=str(user.id), email=user.email)


async def verify_magic_link(
    session: AsyncSession, *, raw_token: str
) -> tuple[UserModel, MagicLinkModel]:
    """Consume a magic-link token and return its owner.

    Raises:
        MagicLinkNotFoundError: no token matches the hash, or the user was
            deleted between issue and verify.
        MagicLinkExpiredError: token is past its TTL.
        MagicLinkAlreadyUsedError: token has been consumed before.
    """
    token_hash = _hash_token(raw_token)
    link_result = await session.execute(
        select(MagicLinkModel).where(MagicLinkModel.token_hash == token_hash)
    )
    link = link_result.scalar_one_or_none()
    if link is None:
        raise MagicLinkNotFoundError()
    if link.consumed_at is not None:
        raise MagicLinkAlreadyUsedError()
    if link.expires_at < datetime.now(UTC):
        raise MagicLinkExpiredError()

    user_result = await session.execute(select(UserModel).where(UserModel.id == link.user_id))
    user = user_result.scalar_one_or_none()
    if user is None or user.deleted_at is not None:
        # Token exists but the user was deleted in the meantime.
        raise MagicLinkNotFoundError()

    link.consumed_at = datetime.now(UTC)
    await session.commit()
    return user, link


__all__ = [
    "MagicLinkAlreadyUsedError",
    "MagicLinkExpiredError",
    "MagicLinkNotFoundError",
    "VerifiedUser",
    "request_magic_link",
    "verify_magic_link",
]
