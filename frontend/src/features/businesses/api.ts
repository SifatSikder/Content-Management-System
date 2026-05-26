import { apiFetchAuthed } from "@/lib/api-client";

import type {
  Business,
  BusinessListResponse,
  CreateBusinessBody,
  InitLogoUploadResponse,
  MeBusinessesResponse,
  UpdateBusinessBody,
} from "./types";

export function listBusinesses(): Promise<BusinessListResponse> {
  return apiFetchAuthed<BusinessListResponse>("/businesses");
}

export function getBusiness(id: string): Promise<Business> {
  return apiFetchAuthed<Business>(`/businesses/${id}`);
}

export function createBusiness(body: CreateBusinessBody): Promise<Business> {
  return apiFetchAuthed<Business>("/businesses", {
    method: "POST",
    body: body as unknown as BodyInit,
  });
}

export function updateBusiness(id: string, body: UpdateBusinessBody): Promise<Business> {
  return apiFetchAuthed<Business>(`/businesses/${id}`, {
    method: "PATCH",
    body: body as unknown as BodyInit,
  });
}

export function deleteBusiness(id: string): Promise<void> {
  return apiFetchAuthed<void>(`/businesses/${id}`, { method: "DELETE" });
}

export function createLogoUploadSession(
  businessId: string,
  body: { content_type: string; size_bytes: number },
): Promise<InitLogoUploadResponse> {
  return apiFetchAuthed<InitLogoUploadResponse>(
    `/businesses/${businessId}/logo/upload-session`,
    {
      method: "POST",
      body: body as unknown as BodyInit,
    },
  );
}

export function finaliseLogoUpload(
  businessId: string,
  body: { gcs_object_name: string },
): Promise<Business> {
  return apiFetchAuthed<Business>(`/businesses/${businessId}/logo/finalise`, {
    method: "POST",
    body: body as unknown as BodyInit,
  });
}

export function removeBusinessLogo(businessId: string): Promise<Business> {
  return apiFetchAuthed<Business>(`/businesses/${businessId}/logo`, {
    method: "DELETE",
  });
}

export function listMyBusinesses(): Promise<MeBusinessesResponse> {
  return apiFetchAuthed<MeBusinessesResponse>("/me/businesses");
}

/**
 * Soft-toggle a business membership between active and revoked. Used by
 * the dept members table's Make active / Make inactive actions — keeps
 * the row + the user's department-level role assignments intact while
 * blocking them at the business gate.
 */
export function setBusinessMembershipStatus(
  businessId: string,
  membershipId: string,
  status: "active" | "revoked",
): Promise<unknown> {
  return apiFetchAuthed(
    `/businesses/${businessId}/memberships/${membershipId}`,
    {
      method: "PATCH",
      body: { status } as unknown as BodyInit,
    },
  );
}
