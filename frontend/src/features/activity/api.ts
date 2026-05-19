import { apiFetchAuthed } from "@/lib/api-client";

import type { ActivityListResponse } from "./types";

export function listProjectActivity(
  projectId: string,
  params: { cursor?: string; limit?: number } = {},
): Promise<ActivityListResponse> {
  const usp = new URLSearchParams();
  if (params.cursor) usp.set("cursor", params.cursor);
  if (params.limit !== undefined) usp.set("limit", String(params.limit));
  const suffix = usp.toString() ? `?${usp.toString()}` : "";
  return apiFetchAuthed<ActivityListResponse>(`/projects/${projectId}/activity${suffix}`);
}
