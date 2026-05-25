import { apiFetchAuthed, ApiError } from "@/lib/api-client";

import type {
  AttachDriveBody,
  DriveConnection,
  DriveDocumentContent,
  DriveDocumentListResponse,
  StartConnectResponse,
} from "./types";

export function listDriveDocuments(
  query?: string,
  limit = 50,
): Promise<DriveDocumentListResponse> {
  const params = new URLSearchParams();
  if (query) params.set("q", query);
  params.set("limit", String(limit));
  return apiFetchAuthed<DriveDocumentListResponse>(`/drive/documents?${params}`);
}

/**
 * Fetch one Google Doc as TipTap-compatible HTML. Does NOT create a script
 * version — the editor loads this as an unsaved draft and the user persists
 * it via the regular "Save new version" path.
 */
export function fetchDriveDocumentContent(
  documentId: string,
): Promise<DriveDocumentContent> {
  return apiFetchAuthed<DriveDocumentContent>(
    `/drive/documents/${encodeURIComponent(documentId)}/content`,
  );
}

export function startDriveConnect(): Promise<StartConnectResponse> {
  return apiFetchAuthed<StartConnectResponse>("/auth/google/drive/start", {
    method: "POST",
  });
}

/**
 * Returns the calling user's Drive connection or `null` if there is none.
 * The backend uses 404 to mean "not connected" — translate to null here so
 * call sites don't have to special-case ApiError everywhere.
 */
export async function getDriveConnection(): Promise<DriveConnection | null> {
  try {
    return await apiFetchAuthed<DriveConnection>("/auth/google/drive/me");
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}

export function disconnectDrive(): Promise<void> {
  return apiFetchAuthed<void>("/auth/google/drive/disconnect", {
    method: "DELETE",
  });
}

export function attachDriveFolder(
  projectId: string,
  body: AttachDriveBody,
): Promise<unknown> {
  return apiFetchAuthed(`/projects/${projectId}/drive/attach`, {
    method: "POST",
    body: body as unknown as BodyInit,
  });
}

export function detachDriveFolder(projectId: string): Promise<unknown> {
  return apiFetchAuthed(`/projects/${projectId}/drive/attach`, {
    method: "DELETE",
  });
}

