/**
 * POST /api/auth/request-reset — start a password-reset flow.
 *
 * Public endpoint. Anti-enumeration: returns 200 OK regardless of whether the
 * email is on file. If it is, mint a password-reset token and email it via
 * Gmail. If Gmail is unconfigured, log the URL to the server stdout and still
 * return 200 — the admin can grab the link from the dev console.
 */

import { NextResponse } from "next/server";

import {
  EmailNotConfiguredError,
  sendPasswordResetEmail,
} from "@/server/email";
import { mintToken } from "@/server/tokens";
import { getActiveUserByEmail } from "@/server/users";

import { jsonError } from "@/server/auth-guard";

interface Body {
  email?: string;
}

const RESET_TTL_SECONDS = Number(process.env.PASSWORD_RESET_TTL_SECONDS ?? 3600);

function resetUrlFor(token: string): string {
  const base =
    process.env.NEXT_PUBLIC_APP_URL ??
    process.env.APP_BASE_URL ??
    "http://localhost:3001";
  return `${base.replace(/\/$/, "")}/reset-password?token=${encodeURIComponent(token)}`;
}

export async function POST(request: Request): Promise<NextResponse> {
  let body: Body;
  try {
    body = (await request.json()) as Body;
  } catch {
    return jsonError(400, "invalid json");
  }
  const email = body.email?.trim();
  if (!email) return jsonError(400, "email is required");

  const user = await getActiveUserByEmail(email);
  if (!user || !user.accepted_at) {
    // Anti-enumeration — say OK regardless.
    return NextResponse.json({ status: "ok" });
  }

  const token = await mintToken({
    userId: user.id,
    purpose: "password_reset",
    ttlSeconds: RESET_TTL_SECONDS,
  });
  const url = resetUrlFor(token);

  try {
    await sendPasswordResetEmail({ to: user.email, resetUrl: url });
  } catch (err) {
    if (err instanceof EmailNotConfiguredError) {
      // Fall back to console-logged URL so dev can proceed before Gmail is set up.
      console.log("[email:fallback] password-reset URL:", url);
    } else {
      throw err;
    }
  }
  return NextResponse.json({ status: "ok" });
}
