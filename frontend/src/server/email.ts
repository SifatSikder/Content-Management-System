/**
 * Gmail send — Next.js side.
 *
 * Uses the same `GMAIL_OAUTH_*` env vars as the backend. Refresh token is
 * obtained once via `scripts/setup_gmail_oauth.py` and stored in `.env.local`.
 *
 * If Gmail isn't configured (e.g. before the CEO has set up GCP credentials),
 * `EmailNotConfiguredError` is raised. The invite/reset route handlers catch
 * it and return the would-be link in the API response so the admin can hand-
 * deliver during bootstrap.
 */

import { google } from "googleapis";

export class EmailNotConfiguredError extends Error {
  constructor() {
    super(
      "Gmail send is not configured. Run scripts/setup_gmail_oauth.py and " +
        "set GMAIL_OAUTH_CLIENT_ID / GMAIL_OAUTH_CLIENT_SECRET / " +
        "GMAIL_OAUTH_REFRESH_TOKEN / GMAIL_SENDER_ADDRESS in .env.local.",
    );
    this.name = "EmailNotConfiguredError";
  }
}

function readConfig(): {
  clientId: string;
  clientSecret: string;
  refreshToken: string;
  sender: string;
} {
  const clientId = process.env.GMAIL_OAUTH_CLIENT_ID;
  const clientSecret = process.env.GMAIL_OAUTH_CLIENT_SECRET;
  const refreshToken = process.env.GMAIL_OAUTH_REFRESH_TOKEN;
  const sender = process.env.GMAIL_SENDER_ADDRESS;
  if (!clientId || !clientSecret || !refreshToken || !sender) {
    throw new EmailNotConfiguredError();
  }
  return { clientId, clientSecret, refreshToken, sender };
}

function gmailClient() {
  const { clientId, clientSecret, refreshToken } = readConfig();
  const oauth2 = new google.auth.OAuth2(clientId, clientSecret);
  oauth2.setCredentials({ refresh_token: refreshToken });
  return google.gmail({ version: "v1", auth: oauth2 });
}

function rfc822Encode(value: string): string {
  return Buffer.from(value, "utf-8").toString("base64url");
}

function buildMessage(opts: { to: string; subject: string; html: string }): string {
  const { sender } = readConfig();
  const lines = [
    `To: ${opts.to}`,
    // RFC 5322 display-name + addr-spec so the inbox shows "Atlas" instead
    // of the raw sender mailbox.
    `From: Atlas <${sender}>`,
    `Subject: ${opts.subject}`,
    "MIME-Version: 1.0",
    'Content-Type: text/html; charset="utf-8"',
    "",
    opts.html,
  ];
  return rfc822Encode(lines.join("\r\n"));
}

async function sendHtmlEmail(opts: { to: string; subject: string; html: string }): Promise<void> {
  const raw = buildMessage(opts);
  await gmailClient().users.messages.send({ userId: "me", requestBody: { raw } });
}

// --- Branded templates -------------------------------------------------------

const _BG = "#f5f5f4";
const _CARD = "#ffffff";
const _TEXT = "#111111";
const _MUTED = "#666666";
const _ACCENT = "#111111";
const _ACCENT_TEXT = "#ffffff";

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function brandedShell(opts: {
  preheader: string;
  heading: string;
  body: string;
  cta: string;
  link: string;
  fallbackIntro: string;
  ttlNote: string;
  footer: string;
}): string {
  const safeLink = escapeHtml(opts.link);
  return `<!doctype html>
<html lang="en">
  <head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${escapeHtml(opts.heading)}</title></head>
  <body style="margin:0;padding:0;background:${_BG};font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:${_TEXT};">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;">${escapeHtml(opts.preheader)}</div>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:${_BG};padding:32px 16px;">
      <tr><td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:520px;background:${_CARD};border-radius:12px;box-shadow:0 1px 3px rgba(0,0,0,0.08);overflow:hidden;">
          <tr><td style="padding:32px 32px 8px 32px;">
            <div style="font-size:13px;letter-spacing:0.06em;text-transform:uppercase;color:${_MUTED};margin-bottom:8px;">Atlas</div>
            <h1 style="margin:0 0 12px 0;font-size:22px;font-weight:600;color:${_TEXT};">${escapeHtml(opts.heading)}</h1>
            <p style="margin:0 0 24px 0;font-size:15px;line-height:1.55;color:${_TEXT};">${escapeHtml(opts.body)}</p>
            <p style="margin:0 0 24px 0;"><a href="${safeLink}" style="display:inline-block;padding:12px 22px;background:${_ACCENT};color:${_ACCENT_TEXT};text-decoration:none;border-radius:8px;font-weight:600;font-size:15px;">${escapeHtml(opts.cta)}</a></p>
            <p style="margin:0 0 8px 0;font-size:13px;color:${_MUTED};">${escapeHtml(opts.fallbackIntro)}</p>
            <p style="margin:0 0 24px 0;font-size:13px;color:${_TEXT};word-break:break-all;"><a href="${safeLink}" style="color:${_TEXT};">${safeLink}</a></p>
            <p style="margin:0 0 4px 0;font-size:12px;color:${_MUTED};">${escapeHtml(opts.ttlNote)}</p>
          </td></tr>
          <tr><td style="padding:16px 32px 24px 32px;border-top:1px solid #eeece8;">
            <p style="margin:0;font-size:12px;line-height:1.5;color:${_MUTED};">${escapeHtml(opts.footer)}</p>
          </td></tr>
        </table>
      </td></tr>
    </table>
  </body>
</html>`;
}

export async function sendInvitationEmail(opts: {
  to: string;
  inviteeName: string;
  inviterName: string;
  acceptUrl: string;
}): Promise<void> {
  const subject = `${opts.inviterName} has invited you to Atlas`;
  const html = brandedShell({
    preheader: "Activate your account. The link is valid for 7 days.",
    heading: `Welcome, ${opts.inviteeName}`,
    body: `${opts.inviterName} has invited you to join Atlas. Click the button below to set a password and activate your account.`,
    cta: "Activate account",
    link: opts.acceptUrl,
    fallbackIntro: "Button not working? Copy this URL into your browser:",
    ttlNote: "This link is valid for 7 days and can be used only once.",
    footer: "You received this email because someone invited you to Atlas. If this wasn't expected, ignore this email.",
  });
  await sendHtmlEmail({ to: opts.to, subject, html });
}

export async function sendPasswordResetEmail(opts: {
  to: string;
  resetUrl: string;
}): Promise<void> {
  const subject = "Reset your Atlas password";
  const html = brandedShell({
    preheader: "Reset your password. The link is valid for 1 hour.",
    heading: "Reset your password",
    body: "Click the button below to set a new password. If you didn't request this, you can safely ignore this email.",
    cta: "Set new password",
    link: opts.resetUrl,
    fallbackIntro: "Button not working? Copy this URL into your browser:",
    ttlNote: "This link is valid for 1 hour and can be used only once.",
    footer: "If you didn't request a password reset, no further action is needed.",
  });
  await sendHtmlEmail({ to: opts.to, subject, html });
}
