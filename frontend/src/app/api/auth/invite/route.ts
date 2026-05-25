/**
 * POST /api/auth/invite — CEO creates a pending user + emails an invitation.
 *
 * Body: { email, name, role }. Role can be any of the spec §6 roles except
 * `ceo` (handing CEO admin to someone new should never happen via the form;
 * it would be a promotion, not an invite).
 *
 * Response on success (200): { user_id, invite_url_for_admin? }.
 * `invite_url_for_admin` is only present when Gmail isn't configured, so the
 * CEO can hand-deliver the link during initial bootstrap.
 */

import { NextResponse } from "next/server";

import { EmailNotConfiguredError, sendInvitationEmail } from "@/server/email";
import { mintToken } from "@/server/tokens";
import { findOrCreateInvitedUser, getActiveUserById } from "@/server/users";

import { jsonError, requireRole } from "@/server/auth-guard";
import { ROLES, type Role } from "@/features/auth/constants";

interface Body {
  email?: string;
  name?: string;
  role?: string;
}

const INVITATION_TTL_SECONDS = Number(process.env.INVITATION_TTL_SECONDS ?? 7 * 24 * 3600);
const ACCEPTABLE_ROLES: ReadonlySet<Role> = new Set(
  ROLES.filter((r) => r !== "ceo"),
);

function acceptUrlFor(token: string): string {
  const base =
    process.env.NEXT_PUBLIC_APP_URL ??
    process.env.APP_BASE_URL ??
    "http://localhost:3001";
  return `${base.replace(/\/$/, "")}/accept-invite?token=${encodeURIComponent(token)}`;
}

export async function POST(request: Request): Promise<NextResponse> {
  const me = await requireRole("ceo");
  if (me instanceof NextResponse) return me;

  let body: Body;
  try {
    body = (await request.json()) as Body;
  } catch {
    return jsonError(400, "invalid json");
  }
  const email = body.email?.trim();
  const name = body.name?.trim();
  const role = body.role?.trim() as Role | undefined;
  if (!email || !name || !role) return jsonError(400, "email, name, role are required");
  if (!ACCEPTABLE_ROLES.has(role)) return jsonError(400, "invalid role");

  const { id: userId, alreadyAccepted } = await findOrCreateInvitedUser({
    email,
    name,
    role,
    invitedBy: me.id,
  });
  if (alreadyAccepted) {
    return jsonError(409, "user has already accepted an invitation");
  }

  const inviter = await getActiveUserById(me.id);
  const token = await mintToken({
    userId,
    purpose: "invitation",
    ttlSeconds: INVITATION_TTL_SECONDS,
  });
  const url = acceptUrlFor(token);

  let usedFallback = false;
  try {
    await sendInvitationEmail({
      to: email,
      inviteeName: name,
      inviterName: inviter?.name ?? "Atlas",
      acceptUrl: url,
    });
  } catch (err) {
    if (err instanceof EmailNotConfiguredError) {
      usedFallback = true;
      console.log(`[email:fallback] invitation URL for ${email}:`, url);
    } else {
      throw err;
    }
  }

  return NextResponse.json({
    user_id: userId,
    invite_url_for_admin: usedFallback ? url : undefined,
  });
}
