/**
 * GET /api/auth/users — CEO lists all (non-deleted) users.
 *
 * Each row includes invitation status so the admin UI can show "pending /
 * accepted" badges and offer the right action (Resend vs Remove).
 */

import { NextResponse } from "next/server";

import { requireRole } from "@/server/auth-guard";
import { listAllUsers } from "@/server/users";

export async function GET(): Promise<NextResponse> {
  const me = await requireRole("ceo");
  if (me instanceof NextResponse) return me;

  const users = await listAllUsers();
  return NextResponse.json({
    items: users.map((u) => ({
      id: u.id,
      email: u.email,
      name: u.name,
      role: u.role,
      created_at: u.created_at,
      invited_at: u.invited_at,
      accepted_at: u.accepted_at,
      last_login_at: u.last_login_at,
      status: u.accepted_at ? "active" : u.invited_at ? "pending" : "unknown",
    })),
  });
}
