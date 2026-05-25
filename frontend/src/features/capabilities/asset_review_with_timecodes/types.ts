/**
 * Lifecycle of a single uploaded cut. Mirror of the Postgres `edit_status`
 * enum on `edit_versions.status`.
 */
export type EditStatus = "in_review" | "changes_requested" | "approved";

export interface EditVersion {
  id: string;
  project_id: string;
  version_number: number;
  uploader_id: string;
  gcs_bucket: string;
  gcs_object_name: string;
  content_type: string;
  size_bytes: number;
  status: EditStatus;
  notes: string | null;
  approved_at: string | null;
  approved_by: string | null;
  resolved_comments: string[];
  created_at: string;
  updated_at: string;
}

export interface EditComment {
  id: string;
  edit_version_id: string;
  author_id: string;
  timestamp_seconds: number;
  body: string;
  resolved_at: string | null;
  resolved_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface InitUploadBody {
  content_type: string;
  size_bytes: number;
  filename?: string | null;
}

export interface InitUploadResponse {
  upload_session_url: string;
  gcs_bucket: string;
  gcs_object_name: string;
  chunk_size_bytes: number;
}

export interface FinaliseEditBody {
  gcs_bucket: string;
  gcs_object_name: string;
  content_type: string;
  size_bytes: number;
  notes?: string | null;
  resolved_comments?: string[];
}

export interface PlaybackUrlResponse {
  url: string;
  expires_in_seconds: number;
}
