/**
 * POST /api/auth/accept-invite — invitee sets their password.
 *
 * Public endpoint (the invitee isn't signed in yet). Consumes the invitation
 * token and writes the bcrypt password hash + accepted_at on the user row.
 * Returns `{status:"ok", email}` so the client can redirect to login.
 */

import { NextResponse } from "next/server";

import {
  PasswordTooLongError,
  PasswordTooShortError,
  hashPassword,
} from "@/server/password";
import {
  TokenAlreadyUsedError,
  TokenExpiredError,
  TokenNotFoundError,
  consumeToken,
} from "@/server/tokens";
import { acceptInvitedUser, getActiveUserById } from "@/server/users";

import { jsonError } from "@/server/auth-guard";

interface Body {
  token?: string;
  password?: string;
  name?: string;
}

export async function POST(request: Request): Promise<NextResponse> {
  let body: Body;
  try {
    body = (await request.json()) as Body;
  } catch {
    return jsonError(400, "invalid json");
  }
  const { token, password, name } = body;
  if (!token || !password) return jsonError(400, "token and password are required");

  let userId: string;
  try {
    ({ userId } = await consumeToken({ raw: token, purpose: "invitation" }));
  } catch (err) {
    if (err instanceof TokenNotFoundError) return jsonError(400, "Invitation not found");
    if (err instanceof TokenExpiredError) return jsonError(400, "Invitation expired");
    if (err instanceof TokenAlreadyUsedError) return jsonError(400, "Invitation already used");
    throw err;
  }

  let passwordHash: string;
  try {
    passwordHash = await hashPassword(password);
  } catch (err) {
    if (err instanceof PasswordTooShortError || err instanceof PasswordTooLongError) {
      return jsonError(400, err.message);
    }
    throw err;
  }

  await acceptInvitedUser({ userId, passwordHash, name });
  const user = await getActiveUserById(userId);
  return NextResponse.json({ status: "ok", email: user?.email ?? null });
}
