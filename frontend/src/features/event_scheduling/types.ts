export type ShootStatus = "scheduled" | "in_progress" | "wrapped";

export interface Shoot {
  id: string;
  project_id: string;
  scheduled_at: string | null;
  call_sheet_object_name: string | null;
  status: ShootStatus;
  started_at: string | null;
  wrapped_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateShootBody {
  scheduled_at?: string | null;
}

export interface UpdateShootBody {
  scheduled_at?: string | null;
}

export interface InitCallSheetUploadBody {
  content_type: string;
  size_bytes: number;
}

export interface InitCallSheetUploadResponse {
  upload_session_url: string;
  gcs_bucket: string;
  gcs_object_name: string;
}

export interface FinaliseCallSheetBody {
  gcs_bucket: string;
  gcs_object_name: string;
}

export interface RawCutSubmission {
  id: string;
  project_id: string;
  shoot_id: string | null;
  uploader_id: string;
  uploader: { id: string; email: string; name: string; role: string };
  gcs_bucket: string;
  gcs_object_name: string;
  original_filename: string | null;
  content_type: string | null;
  byte_size: number | null;
  submitted_at: string;
}
