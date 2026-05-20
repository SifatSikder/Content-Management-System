import { localFetch } from "@/lib/api-client";

import type {
  AcceptInviteBody,
  ChangePasswordBody,
  RequestResetBody,
  ResetPasswordBody,
} from "./types";

/**
 * Auth API — all endpoints live under /api/auth on the Next.js side.
 *
 * Login + logout don't appear here because they're handled directly by
 * `signIn()` / `signOut()` from `next-auth/react`, which posts to the
 * NextAuth-owned routes (/api/auth/callback/credentials, /api/auth/signout).
 *
 * Anonymous flows (accept-invite, request-reset, reset) use `apiFetch` against
 * `/api/auth/*` — since the path is absolute (starts with `/api`), api-client
 * leaves it relative to the current origin rather than prepending the FastAPI
 * base URL. `localFetch` is used for authed change-password since it ships the
 * session cookie via `credentials: "include"`.
 */

export function acceptInvite(body: AcceptInviteBody): Promise<{ status: string }> {
  return localFetch("/api/auth/accept-invite", {
    method: "POST",
    body: body as unknown as BodyInit,
  });
}

export function requestPasswordReset(body: RequestResetBody): Promise<{ status: string }> {
  return localFetch("/api/auth/request-reset", {
    method: "POST",
    body: body as unknown as BodyInit,
  });
}

export function resetPassword(body: ResetPasswordBody): Promise<{ status: string }> {
  return localFetch("/api/auth/reset", {
    method: "POST",
    body: body as unknown as BodyInit,
  });
}

export function changePassword(body: ChangePasswordBody): Promise<{ status: string }> {
  return localFetch("/api/auth/change-password", {
    method: "POST",
    body: body as unknown as BodyInit,
  });
}
