"""Generate a VAPID keypair for Web Push (dev one-shot).

Prints PEM-encoded private + public keys and a `VAPID_SUBJECT=mailto:...`
line. Paste the three lines into `.env.local`. Re-run only if you need to
rotate the keypair (which invalidates all existing browser subscriptions).
"""

from __future__ import annotations

import sys

from py_vapid import Vapid


def main() -> None:
    v = Vapid()
    v.generate_keys()
    private_pem = v.private_pem().decode().strip()
    public_pem = v.public_pem().decode().strip()

    print("# --- Add these to .env.local (and never commit them) ---")
    print(f"VAPID_PRIVATE_PEM={private_pem!r}")
    print(f"VAPID_PUBLIC_PEM={public_pem!r}")
    print('VAPID_SUBJECT=mailto:ceo@example.com  # adjust to a real contact mailbox')


if __name__ == "__main__":
    sys.exit(main())
