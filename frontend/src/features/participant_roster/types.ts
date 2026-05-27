export interface CastMember {
  id: string;
  project_id: string;
  name: string;
  role_description: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  release_form_object_name: string | null;
  kind: "cast" | "lead";
  source: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateCastBody {
  name: string;
  role_description?: string | null;
  contact_email?: string | null;
  contact_phone?: string | null;
  /** "cast" (default) renders the casting form; "lead" renders the leaner lead form. */
  kind?: "cast" | "lead";
  source?: string | null;
  notes?: string | null;
}

export interface InitReleaseUploadBody {
  content_type: string;
  size_bytes: number;
}

export interface InitReleaseUploadResponse {
  upload_session_url: string;
  gcs_bucket: string;
  gcs_object_name: string;
}

export interface FinaliseReleaseBody {
  gcs_bucket: string;
  gcs_object_name: string;
  content_type: string;
  size_bytes: number;
}
