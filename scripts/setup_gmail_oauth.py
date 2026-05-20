"""One-time helper: obtain a Gmail send refresh token via a Web-app OAuth client.

Walks the operator through Google's OAuth2 authorization-code flow once. The
refresh token it prints is long-lived (effectively until revoked) and goes
into `.env.local` as GMAIL_OAUTH_REFRESH_TOKEN. Both the backend and the
Next.js layer use the same triplet (client_id + client_secret + refresh_token)
plus the GMAIL_SENDER_ADDRESS to send mail "as" the CEO mailbox.

We use a **Web application** OAuth client (not Desktop) — that's the
production-appropriate client type. The setup is slightly more ceremonious
(you must register the redirect URI in advance), but it matches what a real
server-side sender requires and aligns with where Google is steering the
ecosystem.

# Prerequisites (one-time, in Google Cloud Console)

1. Create or reuse a project.
2. Enable the Gmail API (APIs & Services → Library → Gmail API).
3. Configure the OAuth consent screen:
     - User type: External
     - Add the CEO mailbox (e.g. sifatsikder2814@gmail.com) as a Test User
     - Scopes: include `https://www.googleapis.com/auth/gmail.send`
4. Create an OAuth 2.0 Client ID:
     - **Application type: Web application** (NOT Desktop)
     - Authorized redirect URIs: add EXACTLY
       `http://localhost:{REDIRECT_PORT}/oauth/gmail/callback`
       Defaults: port 8765, path /oauth/gmail/callback. Override via
       GMAIL_OAUTH_REDIRECT_PORT and GMAIL_OAUTH_REDIRECT_PATH env vars.
     - Download the resulting `client_secret.json`.

# Usage

    uv run python scripts/setup_gmail_oauth.py /path/to/client_secret.json

The script opens your browser, you sign in as the sender mailbox, grant the
gmail.send scope, and the script prints the credentials to paste into
`.env.local`.

# Note on send volumes / commercial scale

Gmail API via a personal Google account caps daily send at ~2000 messages
(varies with reputation). For a 3-6-person internal CMS that's plenty. If
this product later moves into customer-facing transactional mail at scale,
swap the Gmail backend for a dedicated ESP (Resend / SendGrid / SES) — the
abstraction in `server/email.ts` + `app/services/email_service.py` makes
that a contained change.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
DEFAULT_REDIRECT_PORT = 8765
DEFAULT_REDIRECT_PATH = "/oauth/gmail/callback"


def main() -> None:
    if len(sys.argv) != 2:
        print(
            "usage: uv run python scripts/setup_gmail_oauth.py <client_secret.json>",
            file=sys.stderr,
        )
        sys.exit(2)

    client_file = Path(sys.argv[1])
    if not client_file.is_file():
        print(f"client secret file not found: {client_file}", file=sys.stderr)
        sys.exit(2)

    raw = json.loads(client_file.read_text(encoding="utf-8"))
    if "web" not in raw:
        # We deliberately require a Web-application client (production-shaped),
        # not a Desktop client. Fail loudly if the JSON looks wrong.
        kind = "Desktop ('installed')" if "installed" in raw else f"unknown ({list(raw)})"
        print(
            f"This script expects a Web-application OAuth client; got a {kind} client.\n"
            "Re-create the OAuth client in GCP as type 'Web application' and download "
            "its client_secret.json. See the module docstring for details.",
            file=sys.stderr,
        )
        sys.exit(2)
    client_id = raw["web"]["client_id"]
    client_secret = raw["web"]["client_secret"]

    redirect_port = int(os.environ.get("GMAIL_OAUTH_REDIRECT_PORT", DEFAULT_REDIRECT_PORT))
    redirect_path = os.environ.get("GMAIL_OAUTH_REDIRECT_PATH", DEFAULT_REDIRECT_PATH)
    if not redirect_path.startswith("/"):
        redirect_path = "/" + redirect_path
    registered_redirects = raw["web"].get("redirect_uris", [])
    expected_redirect = f"http://localhost:{redirect_port}{redirect_path}"
    if expected_redirect not in registered_redirects:
        print(
            f"\nThe redirect URI {expected_redirect!r} is not registered on this OAuth client.\n"
            f"Currently-registered redirect URIs: {registered_redirects or '(none)'}\n\n"
            "Open the OAuth client in GCP → Credentials → edit → 'Authorized redirect URIs'\n"
            f"and add exactly: {expected_redirect}\n"
            "Path + port must match exactly (case- and trailing-slash-sensitive). "
            "Re-download client_secret.json after saving.",
            file=sys.stderr,
        )
        sys.exit(2)

    try:
        from google_auth_oauthlib.flow import Flow  # type: ignore[import-untyped]
    except ImportError:
        print(
            "google-auth-oauthlib is required. Install it with:\n"
            "    uv add google-auth-oauthlib",
            file=sys.stderr,
        )
        sys.exit(2)

    flow = Flow.from_client_secrets_file(
        str(client_file), scopes=SCOPES, redirect_uri=expected_redirect
    )
    auth_url, _state = flow.authorization_url(
        access_type="offline", prompt="consent", include_granted_scopes="false"
    )

    print("Open this URL in a browser logged in as the sender mailbox:\n")
    print(auth_url)
    print()
    print(
        "After approving, your browser will be redirected to "
        f"{expected_redirect}?code=…\nCopy the full URL from the address bar and paste it below."
    )
    full_url = input("\nFull redirected URL: ").strip()

    flow.fetch_token(authorization_response=full_url)
    creds = flow.credentials
    if not creds.refresh_token:
        print(
            "Google didn't return a refresh token. This usually means you've already "
            "granted access to this client before. Revoke access at "
            "https://myaccount.google.com/permissions and try again.",
            file=sys.stderr,
        )
        sys.exit(2)

    print()
    print("=" * 72)
    print("Add these lines to .env.local (and keep them secret):")
    print("=" * 72)
    print(f"GMAIL_OAUTH_CLIENT_ID={client_id}")
    print(f"GMAIL_OAUTH_CLIENT_SECRET={client_secret}")
    print(f"GMAIL_OAUTH_REFRESH_TOKEN={creds.refresh_token}")
    print("GMAIL_SENDER_ADDRESS=sifatsikder2814@gmail.com  # adjust if different")
    print("=" * 72)


if __name__ == "__main__":
    main()
