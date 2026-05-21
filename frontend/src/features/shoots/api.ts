import { apiFetchAuthed } from "@/lib/api-client";

import type {
  CreateShootBody,
  FinaliseCallSheetBody,
  InitCallSheetUploadBody,
  InitCallSheetUploadResponse,
  Shoot,
  UpdateShootBody,
} from "./types";

export function listShoots(projectId: string): Promise<Shoot[]> {
  return apiFetchAuthed<Shoot[]>(`/projects/${projectId}/shoots`);
}

export function createShoot(projectId: string, body: CreateShootBody): Promise<Shoot> {
  return apiFetchAuthed<Shoot>(`/projects/${projectId}/shoots`, {
    method: "POST",
    body: body as unknown as BodyInit,
  });
}

export function updateShoot(shootId: string, body: UpdateShootBody): Promise<Shoot> {
  return apiFetchAuthed<Shoot>(`/shoots/${shootId}`, {
    method: "PATCH",
    body: body as unknown as BodyInit,
  });
}

export function startShoot(shootId: string): Promise<Shoot> {
  return apiFetchAuthed<Shoot>(`/shoots/${shootId}/start`, { method: "POST" });
}

export function wrapShoot(shootId: string): Promise<Shoot> {
  return apiFetchAuthed<Shoot>(`/shoots/${shootId}/wrap`, { method: "POST" });
}

export function deleteShoot(shootId: string): Promise<void> {
  return apiFetchAuthed<void>(`/shoots/${shootId}`, { method: "DELETE" });
}

export function initCallSheetUpload(
  shootId: string,
  body: InitCallSheetUploadBody,
): Promise<InitCallSheetUploadResponse> {
  return apiFetchAuthed<InitCallSheetUploadResponse>(
    `/shoots/${shootId}/call-sheet/init-upload`,
    { method: "POST", body: body as unknown as BodyInit },
  );
}

export function finaliseCallSheet(
  shootId: string,
  body: FinaliseCallSheetBody,
): Promise<Shoot> {
  return apiFetchAuthed<Shoot>(`/shoots/${shootId}/call-sheet`, {
    method: "POST",
    body: body as unknown as BodyInit,
  });
}
