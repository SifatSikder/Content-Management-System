/**
 * Public DTOs for the Atlas multi-business API surface.
 * Mirror `app/schemas/business.py` on the backend.
 */

export type BusinessMembershipStatus = "invited" | "active" | "revoked";

export interface Business {
  id: string;
  name: string;
  slug: string;
  owner_user_id: string;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

export interface BusinessListResponse {
  items: Business[];
}

export interface CreateBusinessBody {
  name: string;
  slug?: string;
}

export interface UpdateBusinessBody {
  name?: string;
  slug?: string;
}

export interface BusinessMembership {
  id: string;
  business_id: string;
  user_id: string;
  status: BusinessMembershipStatus;
  invited_by: string | null;
  joined_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface BusinessMembershipListResponse {
  items: BusinessMembership[];
}

export interface InviteBusinessMemberBody {
  email: string;
}

export interface MeBusinessEntry {
  id: string;
  name: string;
  slug: string;
  is_owner: boolean;
  membership_status: BusinessMembershipStatus | null;
}

export interface MeBusinessesResponse {
  items: MeBusinessEntry[];
}
