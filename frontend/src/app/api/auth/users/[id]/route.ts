/**
 * DELETE /api/auth/users/[id] — CEO soft-deletes a teammate.
 *
 * The CEO cannot soft-delete themselves (would lock the org out). FK cascade
 * on `one_time_tokens` clears any pending invitations.
 */

import { NextResponse } from "next/server";

import { jsonError, requireRole } from "@/server/auth-guard";
import { getActiveUserById, softDeleteUser } from "@/server/users";

export async function DELETE(
  _request: Request,
  ctx: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const me = await requireRole("ceo");
  if (me instanceof NextResponse) return me;

  const { id } = await ctx.params;
  if (id === me.id) return jsonError(400, "cannot remove yourself");

  const target = await getActiveUserById(id);
  if (!target) return jsonError(404, "user not found");

  await softDeleteUser(id);
  return NextResponse.json({ status: "ok" });
}
