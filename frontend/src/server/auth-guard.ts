/**
 * Helpers for /api/auth/* route handlers — uniform auth + role gates plus
 * tidy JSON error shapes that match FastAPI's `{detail, request_id}`.
 */

import { NextResponse } from "next/server";

import { auth } from "@/auth";
import type { Role } from "@/lib/enums";

export function jsonError(status: number, detail: string): NextResponse {
  return NextResponse.json({ detail }, { status });
}

/**
 * Returns the session user id + role, or a 401 NextResponse to throw at the
 * caller. Usage:
 *
 *     const me = await requireSession();
 *     if (me instanceof NextResponse) return me;
 *     // me.id, me.role
 */
export async function requireSession(): Promise<
  { id: string; role: Role } | NextResponse
> {
  const session = await auth();
  if (!session?.user?.id) return jsonError(401, "unauthorized");
  return { id: session.user.id, role: session.user.role };
}

export async function requireRole(
  ...allowed: Role[]
): Promise<{ id: string; role: Role } | NextResponse> {
  const me = await requireSession();
  if (me instanceof NextResponse) return me;
  if (!allowed.includes(me.role)) return jsonError(403, "forbidden");
  return me;
}
