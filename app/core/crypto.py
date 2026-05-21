"""Symmetric encryption for at-rest secrets (OAuth refresh tokens).

Fernet = AES-128-CBC + HMAC-SHA256 (authenticated). The key lives in
`settings.token_encryption_key` (urlsafe-base64 32 bytes). Rotation
invalidates every existing ciphertext, so the per-user `connected_*`
table rows have to be re-created — users reconnect Drive.

Why a separate key from `jwt_secret`: JWT signing is HMAC and the secret
can be rotated independently of long-lived refresh tokens. Mixing the
two means a JWT-secret rotation logs everyone out of Drive too.
"""

from __future__ import annotations

import structlog
from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

log = structlog.get_logger(__name__)


class TokenEncryptionNotConfiguredError(RuntimeError):
    """TOKEN_ENCRYPTION_KEY is missing — refuse to handle refresh tokens."""


class TokenDecryptionError(RuntimeError):
    """Ciphertext could not be decrypted with the current key.

    Most likely cause: the encryption key was rotated after the row was
    written. The connected_google_account row should be deleted and the
    user prompted to reconnect.
    """


def _fernet() -> Fernet:
    key = get_settings().token_encryption_key
    if not key:
        raise TokenEncryptionNotConfiguredError(
            "TOKEN_ENCRYPTION_KEY is unset; refusing to handle OAuth refresh tokens. "
            "Generate one with `uv run python scripts/gen_token_encryption_key.py`."
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_token(plaintext: str) -> str:
    """Return a urlsafe-base64 ciphertext suitable for DB storage."""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    """Decrypt a value previously produced by `encrypt_token`."""
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise TokenDecryptionError(
            "Stored ciphertext could not be decrypted with the current key"
        ) from exc


__all__ = [
    "TokenDecryptionError",
    "TokenEncryptionNotConfiguredError",
    "decrypt_token",
    "encrypt_token",
]
