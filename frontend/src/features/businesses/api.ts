import { apiFetchAuthed } from "@/lib/api-client";

import type {
  Business,
  BusinessListResponse,
  BusinessMembership,
  BusinessMembershipListResponse,
  CreateBusinessBody,
  InviteBusinessMemberBody,
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

export function listMemberships(businessId: string): Promise<BusinessMembershipListResponse> {
  return apiFetchAuthed<BusinessMembershipListResponse>(
    `/businesses/${businessId}/memberships`,
  );
}

export function inviteMember(
  businessId: string,
  body: InviteBusinessMemberBody,
): Promise<BusinessMembership> {
  return apiFetchAuthed<BusinessMembership>(`/businesses/${businessId}/memberships`, {
    method: "POST",
    body: body as unknown as BodyInit,
  });
}

export function revokeMembership(
  businessId: string,
  membershipId: string,
): Promise<void> {
  return apiFetchAuthed<void>(
    `/businesses/${businessId}/memberships/${membershipId}`,
    { method: "DELETE" },
  );
}

export function listMyBusinesses(): Promise<MeBusinessesResponse> {
  return apiFetchAuthed<MeBusinessesResponse>("/me/businesses");
}
