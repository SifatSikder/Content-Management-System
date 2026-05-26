import { apiFetchAuthed } from "@/lib/api-client";

import type {
  CastMember,
  CreateCastBody,
  FinaliseReleaseBody,
  InitReleaseUploadBody,
  InitReleaseUploadResponse,
} from "./types";

export function listCast(projectId: string): Promise<CastMember[]> {
  return apiFetchAuthed<CastMember[]>(`/projects/${projectId}/cast`);
}

export function createCast(projectId: string, body: CreateCastBody): Promise<CastMember> {
  return apiFetchAuthed<CastMember>(`/projects/${projectId}/cast`, {
    method: "POST",
    body: body as unknown as BodyInit,
  });
}

export function confirmCast(castId: string): Promise<CastMember> {
  return apiFetchAuthed<CastMember>(`/cast/${castId}/confirm`, { method: "POST" });
}

export function unconfirmCast(castId: string): Promise<CastMember> {
  return apiFetchAuthed<CastMember>(`/cast/${castId}/unconfirm`, { method: "POST" });
}

export function deleteCast(castId: string): Promise<void> {
  return apiFetchAuthed<void>(`/cast/${castId}`, { method: "DELETE" });
}

export function initReleaseUpload(
  castId: string,
  body: InitReleaseUploadBody,
): Promise<InitReleaseUploadResponse> {
  return apiFetchAuthed<InitReleaseUploadResponse>(`/cast/${castId}/release/init-upload`, {
    method: "POST",
    body: body as unknown as BodyInit,
  });
}

export function finaliseRelease(
  castId: string,
  body: FinaliseReleaseBody,
): Promise<CastMember> {
  return apiFetchAuthed<CastMember>(`/cast/${castId}/release`, {
    method: "POST",
    body: body as unknown as BodyInit,
  });
}

export interface ReleaseUrlResponse {
  url: string;
  content_type: string;
  expires_in_seconds: number;
}

export function getReleaseUrl(castId: string): Promise<ReleaseUrlResponse> {
  return apiFetchAuthed<ReleaseUrlResponse>(`/cast/${castId}/release/url`);
}

export function lockProjectCasting(projectId: string): Promise<{ status: string }> {
  return apiFetchAuthed<{ status: string }>(
    `/projects/${projectId}/cast/lock`,
    { method: "POST" },
  );
}
