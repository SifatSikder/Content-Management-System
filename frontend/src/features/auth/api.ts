import { apiFetch, apiFetchAuthed } from "@/lib/api-client";

import type { AuthUser, RequestLinkBody, VerifyResponse } from "./types";

export function requestLink(body: RequestLinkBody): Promise<{ status: string }> {
  return apiFetch("/auth/request-link", {
    method: "POST",
    body: body as unknown as BodyInit,
  });
}

export function verifyToken(token: string): Promise<VerifyResponse> {
  return apiFetch<VerifyResponse>(`/auth/verify?token=${encodeURIComponent(token)}`);
}

export function fetchMe(): Promise<AuthUser> {
  return apiFetchAuthed<AuthUser>("/auth/me");
}
