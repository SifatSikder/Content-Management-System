/**
 * POST /api/auth/users/[id]/resend — CEO resends a pending invitation.
 *
 * Mints a fresh invitation token (deletes any prior unconsumed one in the
 * same transaction inside `mintToken`) and emails it again.
 */

import { NextResponse } from "next/server";

import { EmailNotConfiguredError, sendInvitationEmail } from "@/server/email";
import { mintToken } from "@/server/tokens";
import { getActiveUserById } from "@/server/users";

import { jsonError, requireRole } from "@/server/auth-guard";

const INVITATION_TTL_SECONDS = Number(process.env.INVITATION_TTL_SECONDS ?? 7 * 24 * 3600);

function acceptUrlFor(token: string): string {
  const base =
    process.env.NEXT_PUBLIC_APP_URL ??
    process.env.APP_BASE_URL ??
    "http://localhost:3001";
  return `${base.replace(/\/$/, "")}/accept-invite?token=${encodeURIComponent(token)}`;
}

export async function POST(
  _request: Request,
  ctx: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const me = await requireRole("ceo");
  if (me instanceof NextResponse) return me;

  const { id } = await ctx.params;
  const target = await getActiveUserById(id);
  if (!target) return jsonError(404, "user not found");
  if (target.accepted_at) return jsonError(409, "user has already accepted");

  const inviter = await getActiveUserById(me.id);
  const token = await mintToken({
    userId: id,
    purpose: "invitation",
    ttlSeconds: INVITATION_TTL_SECONDS,
  });
  const url = acceptUrlFor(token);

  let usedFallback = false;
  try {
    await sendInvitationEmail({
      to: target.email,
      inviteeName: target.name,
      inviterName: inviter?.name ?? "Sons Real Estate",
      acceptUrl: url,
    });
  } catch (err) {
    if (err instanceof EmailNotConfiguredError) {
      usedFallback = true;
      console.log(`[email:fallback] invitation URL for ${target.email}:`, url);
    } else {
      throw err;
    }
  }

  return NextResponse.json({
    user_id: id,
    invite_url_for_admin: usedFallback ? url : undefined,
  });
}
