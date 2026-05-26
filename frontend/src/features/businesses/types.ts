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
  logo_url: string | null;
}

export interface InitLogoUploadResponse {
  upload_session_url: string;
  gcs_bucket: string;
  gcs_object_name: string;
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

export interface MeBusinessEntry {
  id: string;
  name: string;
  slug: string;
  is_owner: boolean;
  membership_status: BusinessMembershipStatus | null;
  logo_url: string | null;
}

export interface MeBusinessesResponse {
  items: MeBusinessEntry[];
}
