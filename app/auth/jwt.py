"""JWT encode/decode helpers.

HS256 with `Settings.jwt_secret`. Claims:
    sub   — user id (str UUID)
    email — user email
    role  — Role.value
    iat   — issued at (unix seconds)
    exp   — expiry (iat + jwt_ttl_seconds)

A bad/expired token raises `InvalidTokenError`; routes translate that into 401.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt

from app.config import Settings, get_settings
from app.models.enums import Role

ALGORITHM = "HS256"


class InvalidTokenError(Exception):
    """Raised when a JWT fails to decode/validate."""


@dataclass(frozen=True)
class AccessTokenClaims:
    sub: uuid.UUID
    email: str
    role: Role
    iat: datetime
    exp: datetime


def issue_access_token(
    *,
    user_id: uuid.UUID,
    email: str,
    role: Role,
    settings: Settings | None = None,
) -> str:
    """Issue a new HS256 access token for the given user."""
    settings = settings or get_settings()
    now = datetime.now(UTC)
    expires = now + timedelta(seconds=settings.jwt_ttl_seconds)
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role.value,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
    }
    token: str = jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)
    return token


def decode_access_token(token: str, *, settings: Settings | None = None) -> AccessTokenClaims:
    """Decode and validate a JWT. Raises InvalidTokenError on any failure."""
    settings = settings or get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise InvalidTokenError(str(exc)) from exc

    try:
        return AccessTokenClaims(
            sub=uuid.UUID(payload["sub"]),
            email=payload["email"],
            role=Role(payload["role"]),
            iat=datetime.fromtimestamp(payload["iat"], tz=UTC),
            exp=datetime.fromtimestamp(payload["exp"], tz=UTC),
        )
    except (KeyError, ValueError) as exc:
        raise InvalidTokenError(f"malformed claims: {exc}") from exc


__all__ = [
    "ALGORITHM",
    "AccessTokenClaims",
    "InvalidTokenError",
    "decode_access_token",
    "issue_access_token",
]
