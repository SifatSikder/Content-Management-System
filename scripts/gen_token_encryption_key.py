"""Generate a Fernet key for encrypting per-user OAuth refresh tokens.

Prints a `TOKEN_ENCRYPTION_KEY=...` line. Paste into `.env.local`. Re-running
rotates the key — any existing `connected_google_accounts` rows become
undecryptable, so users have to reconnect Drive after a rotation.
"""

from __future__ import annotations

import sys

from cryptography.fernet import Fernet


def main() -> None:
    key = Fernet.generate_key().decode()
    print("# --- Add to .env.local (rotation invalidates existing connections) ---")
    print(f"TOKEN_ENCRYPTION_KEY={key}")


if __name__ == "__main__":
    sys.exit(main())
