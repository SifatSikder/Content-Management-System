/**
 * POST /api/auth/change-password
 *
 * Authed endpoint — invoked from the `/change-password` page after a user has
 * signed in (either via initial CEO bootstrap or after accepting an invite).
 * Verifies the current password against the bcrypt hash, then writes the new
 * one and clears `must_change_password`.
 *
 * Returns 200 `{status: "ok"}` on success. The client signs out + back in
 * after a successful change so the JWT cookie's `must_change_password` claim
 * refreshes to false.
 */

import { NextResponse } from "next/server";

import { auth } from "@/auth";
import {
  PasswordTooLongError,
  PasswordTooShortError,
  hashPassword,
  verifyPassword,
} from "@/server/password";
import { getActiveUserById, setPassword } from "@/server/users";

interface Body {
  current_password?: string;
  new_password?: string;
}

export async function POST(request: Request): Promise<NextResponse> {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ detail: "unauthorized" }, { status: 401 });
  }

  let body: Body;
  try {
    body = (await request.json()) as Body;
  } catch {
    return NextResponse.json({ detail: "invalid json" }, { status: 400 });
  }
  const current = body.current_password;
  const next = body.new_password;
  if (!current || !next) {
    return NextResponse.json(
      { detail: "current_password and new_password are required" },
      { status: 400 },
    );
  }

  const user = await getActiveUserById(session.user.id);
  if (!user?.password_hash) {
    return NextResponse.json({ detail: "user not found" }, { status: 401 });
  }
  if (!(await verifyPassword(current, user.password_hash))) {
    return NextResponse.json({ detail: "current password incorrect" }, { status: 400 });
  }

  try {
    const hash = await hashPassword(next);
    await setPassword({ userId: user.id, passwordHash: hash });
  } catch (err) {
    if (err instanceof PasswordTooShortError || err instanceof PasswordTooLongError) {
      return NextResponse.json({ detail: err.message }, { status: 400 });
    }
    throw err;
  }

  return NextResponse.json({ status: "ok" });
}
