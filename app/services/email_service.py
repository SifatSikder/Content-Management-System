"""Email service — magic-link delivery.

Two modes:
  * dev — writes a fully-formed HTML file to `.dev-emails/<timestamp>.html`
    and prints the verification URL to stdout. No external service is called.
  * prod — should call the Resend SDK. Wiring lives in Phase 5 (Task 5.6.1);
    the prod branch here raises `RuntimeError` so a misconfigured deploy
    fails loudly rather than silently dropping mail.

Templates are inlined (no Jinja dependency) and ship in Dutch (default) and
English. They use brand neutrals + a single accent (oklch-friendly hex) so
they render cleanly in any client without external CSS.
"""

from __future__ import annotations

import datetime as dt
import re
from html import escape
from pathlib import Path

import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)

_DEV_EMAIL_DIR = Path(".dev-emails")

# Brand palette (used by the email-only inline CSS).
_BG = "#f5f5f4"
_CARD = "#ffffff"
_TEXT = "#111111"
_MUTED = "#666666"
_ACCENT = "#111111"
_ACCENT_TEXT = "#ffffff"


_NL_COPY = {
    "subject": "Aanmelden bij Sons Real Estate CMS",
    "preheader": "Klik op de knop om je aan te melden. Geldig voor 15 minuten.",
    "heading": "Welkom terug",
    "body": (
        "Klik op de onderstaande knop om je aan te melden bij het "
        "Sons Real Estate productiesysteem."
    ),
    "cta": "Aanmelden",
    "fallback_intro": "Werkt de knop niet? Kopieer dan deze link in je browser:",
    "ttl_note": "Deze link is 15 minuten geldig en kan slechts één keer worden gebruikt.",
    "footer": "Je hebt deze e-mail ontvangen omdat iemand je e-mailadres bij Sons Real Estate heeft ingevoerd. Negeer deze e-mail als je dat niet was.",
}

_EN_COPY = {
    "subject": "Sign in to Sons Real Estate CMS",
    "preheader": "Click the button to sign in. Valid for 15 minutes.",
    "heading": "Welcome back",
    "body": "Click the button below to sign in to the Sons Real Estate production system.",
    "cta": "Sign in",
    "fallback_intro": "Button not working? Copy this link into your browser:",
    "ttl_note": "This link is valid for 15 minutes and can be used only once.",
    "footer": "You received this email because someone entered your address at Sons Real Estate. Ignore it if that wasn't you.",
}


def _ensure_dev_dir() -> None:
    _DEV_EMAIL_DIR.mkdir(parents=True, exist_ok=True)


def _slug_email(addr: str) -> str:
    """Return a filesystem-safe representation of an email address."""
    return re.sub(r"[^A-Za-z0-9_.@-]", "_", addr).replace("@", "_at_")


def _write_dev_email(to: str, subject: str, html: str) -> Path:
    _ensure_dev_dir()
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d-%H%M%S-%f")
    path = _DEV_EMAIL_DIR / f"{stamp}__{_slug_email(to)}.html"
    path.write_text(
        f"<!--\nTO: {to}\nSUBJECT: {subject}\n-->\n{html}",
        encoding="utf-8",
    )
    return path


def _render_magic_link_html(*, link: str, locale: str) -> tuple[str, str]:
    """Return `(subject, html)` for the chosen locale."""
    copy = _NL_COPY if locale.startswith("nl") else _EN_COPY
    safe_link = escape(link, quote=True)
    body_html = f"""
    <!doctype html>
    <html lang="{escape(locale)}">
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width,initial-scale=1">
        <title>{escape(copy["subject"])}</title>
      </head>
      <body style="margin:0;padding:0;background:{_BG};
                   font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
                   color:{_TEXT};">
        <!-- Preheader (hidden, shown by some clients in the preview) -->
        <div style="display:none;max-height:0;overflow:hidden;opacity:0;">
          {escape(copy["preheader"])}
        </div>
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
               style="background:{_BG};padding:32px 16px;">
          <tr>
            <td align="center">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
                     style="max-width:520px;background:{_CARD};border-radius:12px;
                            box-shadow:0 1px 3px rgba(0,0,0,0.08);overflow:hidden;">
                <tr>
                  <td style="padding:32px 32px 8px 32px;">
                    <div style="font-size:13px;letter-spacing:0.06em;text-transform:uppercase;
                                color:{_MUTED};margin-bottom:8px;">
                      Sons Real Estate
                    </div>
                    <h1 style="margin:0 0 12px 0;font-size:22px;font-weight:600;color:{_TEXT};">
                      {escape(copy["heading"])}
                    </h1>
                    <p style="margin:0 0 24px 0;font-size:15px;line-height:1.55;color:{_TEXT};">
                      {escape(copy["body"])}
                    </p>
                    <p style="margin:0 0 24px 0;">
                      <a href="{safe_link}"
                         style="display:inline-block;padding:12px 22px;background:{_ACCENT};
                                color:{_ACCENT_TEXT};text-decoration:none;border-radius:8px;
                                font-weight:600;font-size:15px;">
                        {escape(copy["cta"])}
                      </a>
                    </p>
                    <p style="margin:0 0 8px 0;font-size:13px;color:{_MUTED};">
                      {escape(copy["fallback_intro"])}
                    </p>
                    <p style="margin:0 0 24px 0;font-size:13px;color:{_TEXT};word-break:break-all;">
                      <a href="{safe_link}" style="color:{_TEXT};">{safe_link}</a>
                    </p>
                    <p style="margin:0 0 4px 0;font-size:12px;color:{_MUTED};">
                      {escape(copy["ttl_note"])}
                    </p>
                  </td>
                </tr>
                <tr>
                  <td style="padding:16px 32px 24px 32px;border-top:1px solid #eeece8;">
                    <p style="margin:0;font-size:12px;line-height:1.5;color:{_MUTED};">
                      {escape(copy["footer"])}
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
      </body>
    </html>
    """.strip()
    return copy["subject"], body_html


def send_magic_link(*, to: str, locale: str, link: str) -> None:
    """Send a magic-link email.

    Dev: writes the HTML to `.dev-emails/<timestamp>.html` and prints the link
    to stdout. Prod: raises until Phase 5 wires the Resend SDK.
    """
    settings = get_settings()
    subject, html = _render_magic_link_html(link=link, locale=locale)

    if settings.is_dev:
        path = _write_dev_email(to=to, subject=subject, html=html)
        print(f"\n[email:dev] wrote {path}\n[email:dev] magic-link: {link}\n", flush=True)
        log.info("email_sent_dev", to=to, subject=subject, path=str(path), locale=locale)
        return

    raise RuntimeError(
        "Real email delivery is not configured. Phase 5 wires Resend; see implementation_plan.md."
    )


__all__ = ["send_magic_link"]
