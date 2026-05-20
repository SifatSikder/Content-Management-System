import { localFetch } from "@/lib/api-client";

import type { InvitePayload, InviteResponse, TeamListResponse } from "./types";

export function listTeam(): Promise<TeamListResponse> {
  return localFetch<TeamListResponse>("/api/auth/users");
}

export function inviteMember(body: InvitePayload): Promise<InviteResponse> {
  return localFetch<InviteResponse>("/api/auth/invite", {
    method: "POST",
    body: body as unknown as BodyInit,
  });
}

export function resendInvite(userId: string): Promise<InviteResponse> {
  return localFetch<InviteResponse>(`/api/auth/users/${userId}/resend`, {
    method: "POST",
  });
}

export function removeMember(userId: string): Promise<{ status: string }> {
  return localFetch(`/api/auth/users/${userId}`, { method: "DELETE" });
}
