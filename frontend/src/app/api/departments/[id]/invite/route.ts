/**
 * POST /api/departments/[id]/invite — CEO orchestrates: find-or-create the
 * platform user, send the invite email if pending, then add them to this
 * department via FastAPI.
 *
 * Body: { email, name, role_id }.
 *
 * This is the only entry point for granting a person access — the legacy
 * `/api/auth/invite` Team-page flow is being retired. Business memberships
 * are now derived: `department_service.assign_department_member` auto-
 * creates the matching `business_memberships` row, so the BFF doesn't have
 * to know about it.
 *
 * Response (201): the FastAPI `DepartmentMembershipPublic` payload, plus an
 * `invite_url_for_admin` when Gmail isn't configured so the CEO can hand
 * over the accept link manually during bootstrap.
 */

import { NextResponse } from "next/server";

import { auth } from "@/auth";
import { EmailNotConfiguredError, sendInvitationEmail } from "@/server/email";
import { mintToken } from "@/server/tokens";
import { findOrCreateInvitedUser, getActiveUserById } from "@/server/users";
import { jsonError, requireRole } from "@/server/auth-guard";

const INVITATION_TTL_SECONDS = Number(
  process.env.INVITATION_TTL_SECONDS ?? 7 * 24 * 3600,
);
const FASTAPI_BASE =
  process.env.NEXT_PUBLIC_API_URL?.trim() || "http://localhost:8000";

interface Body {
  email?: string;
  name?: string;
  role_id?: string;
}

function acceptUrlFor(token: string): string {
  const base =
    process.env.NEXT_PUBLIC_APP_URL ??
    process.env.APP_BASE_URL ??
    "http://localhost:3001";
  return `${base.replace(/\/$/, "")}/accept-invite?token=${encodeURIComponent(token)}`;
}

export async function POST(
  request: Request,
  ctx: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const me = await requireRole("ceo");
  if (me instanceof NextResponse) return me;

  const { id: departmentId } = await ctx.params;
  if (!/^[0-9a-f-]{36}$/i.test(departmentId)) {
    return jsonError(400, "invalid department id");
  }

  let body: Body;
  try {
    body = (await request.json()) as Body;
  } catch {
    return jsonError(400, "invalid json");
  }
  const email = body.email?.trim();
  const name = body.name?.trim();
  const roleId = body.role_id?.trim();
  if (!email || !name || !roleId) {
    return jsonError(400, "email, name, role_id are required");
  }

  // Newly invited users have no platform-level privileges — access is granted
  // entirely through their department role(s). `viewer` is the placeholder.
  const { id: userId, alreadyAccepted } = await findOrCreateInvitedUser({
    email,
    name,
    role: "viewer",
    invitedBy: me.id,
  });

  // Send the invitation email unless the user has already accepted a prior
  // invite (i.e. they're already a real platform user — just being added to
  // another department).
  let inviteUrlForAdmin: string | undefined;
  if (!alreadyAccepted) {
    const inviter = await getActiveUserById(me.id);
    const token = await mintToken({
      userId,
      purpose: "invitation",
      ttlSeconds: INVITATION_TTL_SECONDS,
    });
    const url = acceptUrlFor(token);
    try {
      await sendInvitationEmail({
        to: email,
        inviteeName: name,
        inviterName: inviter?.name ?? "Atlas",
        acceptUrl: url,
      });
    } catch (err) {
      if (err instanceof EmailNotConfiguredError) {
        inviteUrlForAdmin = url;
        console.log(`[email:fallback] invitation URL for ${email}:`, url);
      } else {
        throw err;
      }
    }
  }

  // Forward to FastAPI to create the department membership (and idempotently
  // the matching business membership). We reuse the CEO's session cookie as
  // a bearer token — same JWT shape, same secret.
  const session = await auth();
  const accessToken = session?.accessToken;
  if (!accessToken) return jsonError(401, "missing access token");

  const apiResp = await fetch(
    `${FASTAPI_BASE}/departments/${encodeURIComponent(departmentId)}/memberships`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify({ user_id: userId, role_id: roleId }),
    },
  );
  const apiBody = await apiResp.text();
  if (!apiResp.ok) {
    return NextResponse.json(
      apiBody ? JSON.parse(apiBody) : { detail: "membership assign failed" },
      { status: apiResp.status },
    );
  }
  const membership = apiBody ? JSON.parse(apiBody) : null;
  return NextResponse.json(
    { ...membership, invite_url_for_admin: inviteUrlForAdmin },
    { status: 201 },
  );
}
