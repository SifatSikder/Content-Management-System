import { apiFetchAuthed } from "@/lib/api-client";

import type {
  CreateLocationBody,
  FinalisePhotoBody,
  InitPhotoUploadBody,
  InitPhotoUploadResponse,
  Location,
  LocationPhoto,
} from "./types";

export function listLocations(projectId: string): Promise<Location[]> {
  return apiFetchAuthed<Location[]>(`/projects/${projectId}/locations`);
}

export function createLocation(
  projectId: string,
  body: CreateLocationBody,
): Promise<Location> {
  return apiFetchAuthed<Location>(`/projects/${projectId}/locations`, {
    method: "POST",
    body: body as unknown as BodyInit,
  });
}

export function confirmLocation(locationId: string): Promise<Location> {
  return apiFetchAuthed<Location>(`/locations/${locationId}/confirm`, { method: "POST" });
}

export function unconfirmLocation(locationId: string): Promise<Location> {
  return apiFetchAuthed<Location>(`/locations/${locationId}/unconfirm`, { method: "POST" });
}

export function deleteLocation(locationId: string): Promise<void> {
  return apiFetchAuthed<void>(`/locations/${locationId}`, { method: "DELETE" });
}

export function initPhotoUpload(
  locationId: string,
  body: InitPhotoUploadBody,
): Promise<InitPhotoUploadResponse> {
  return apiFetchAuthed<InitPhotoUploadResponse>(
    `/locations/${locationId}/photos/init-upload`,
    { method: "POST", body: body as unknown as BodyInit },
  );
}

export function finalisePhoto(
  locationId: string,
  body: FinalisePhotoBody,
): Promise<LocationPhoto> {
  return apiFetchAuthed<LocationPhoto>(`/locations/${locationId}/photos`, {
    method: "POST",
    body: body as unknown as BodyInit,
  });
}

export function deletePhoto(photoId: string): Promise<void> {
  return apiFetchAuthed<void>(`/locations/photos/${photoId}`, { method: "DELETE" });
}

export function getPhotoUrl(photoId: string): Promise<{ url: string; expires_in_seconds: number }> {
  return apiFetchAuthed<{ url: string; expires_in_seconds: number }>(
    `/locations/photos/${photoId}/url`,
  );
}

export function lockProjectLocation(projectId: string): Promise<{ status: string }> {
  return apiFetchAuthed<{ status: string }>(
    `/projects/${projectId}/locations/lock`,
    { method: "POST" },
  );
}

export function unlockProjectLocation(projectId: string): Promise<{ status: string }> {
  return apiFetchAuthed<{ status: string }>(
    `/projects/${projectId}/locations/unlock`,
    { method: "POST" },
  );
}
