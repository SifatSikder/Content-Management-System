/**
 * POST /api/auth/reset — set new password using a password-reset token.
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
import { setPassword } from "@/server/users";

import { jsonError } from "@/server/auth-guard";

interface Body {
  token?: string;
  password?: string;
}

export async function POST(request: Request): Promise<NextResponse> {
  let body: Body;
  try {
    body = (await request.json()) as Body;
  } catch {
    return jsonError(400, "invalid json");
  }
  const { token, password } = body;
  if (!token || !password) return jsonError(400, "token and password are required");

  let userId: string;
  try {
    ({ userId } = await consumeToken({ raw: token, purpose: "password_reset" }));
  } catch (err) {
    if (err instanceof TokenNotFoundError) return jsonError(400, "Reset link not found");
    if (err instanceof TokenExpiredError) return jsonError(400, "Reset link expired");
    if (err instanceof TokenAlreadyUsedError) return jsonError(400, "Reset link already used");
    throw err;
  }

  let hash: string;
  try {
    hash = await hashPassword(password);
  } catch (err) {
    if (err instanceof PasswordTooShortError || err instanceof PasswordTooLongError) {
      return jsonError(400, err.message);
    }
    throw err;
  }
  await setPassword({ userId, passwordHash: hash });
  return NextResponse.json({ status: "ok" });
}
