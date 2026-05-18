"""Email service.

Phase 0 stub: in dev mode, magic-link emails are written to `.dev-emails/`
and the verification URL is printed to stdout so the developer can iterate
fast. In prod, this module calls Resend (Phase 5 wires the real SDK).
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)

_DEV_EMAIL_DIR = Path(".dev-emails")


def _ensure_dev_dir() -> None:
    _DEV_EMAIL_DIR.mkdir(parents=True, exist_ok=True)


def _write_dev_email(to: str, subject: str, html: str) -> Path:
    _ensure_dev_dir()
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d-%H%M%S-%f")
    safe_to = to.replace("@", "_at_").replace("/", "_")
    path = _DEV_EMAIL_DIR / f"{stamp}__{safe_to}.html"
    path.write_text(
        f"<!--\nTO: {to}\nSUBJECT: {subject}\n-->\n{html}",
        encoding="utf-8",
    )
    return path


def send_magic_link(*, to: str, locale: str, link: str) -> None:
    """Send a magic-link email.

    Phase 0 dev behaviour: writes the message to `.dev-emails/<timestamp>.html`
    AND prints the link to stdout so the developer can click it directly.
    """
    settings = get_settings()

    subject = (
        "Aanmelden bij Sons Real Estate CMS"
        if locale.startswith("nl")
        else "Sign in to Sons Real Estate CMS"
    )
    body_intro = (
        "Klik op de onderstaande knop om je aan te melden. De link is 15 minuten geldig."
        if locale.startswith("nl")
        else "Click the button below to sign in. The link is valid for 15 minutes."
    )
    cta = "Aanmelden" if locale.startswith("nl") else "Sign in"

    html = f"""
    <html><body style="font-family:system-ui,sans-serif;color:#111;">
      <p>{body_intro}</p>
      <p>
        <a href="{link}"
           style="display:inline-block;padding:10px 18px;background:#111;color:#fff;
                  text-decoration:none;border-radius:6px;">{cta}</a>
      </p>
      <p style="font-size:12px;color:#666;">If the button doesn't work, copy this URL:<br>{link}</p>
    </body></html>
    """.strip()

    if settings.is_dev:
        path = _write_dev_email(to=to, subject=subject, html=html)
        print(f"\n[email:dev] wrote {path}\n[email:dev] magic-link: {link}\n", flush=True)
        log.info("email_sent_dev", to=to, subject=subject, path=str(path))
        return

    # Phase 5 will wire the real Resend SDK here. Until then, fail loudly in prod
    # so we don't silently drop production emails.
    raise RuntimeError(
        "Real email delivery is not configured. Phase 5 wires Resend; see implementation_plan.md."
    )
