export interface LocationPhoto {
  id: string;
  location_id: string;
  gcs_bucket: string;
  gcs_object_name: string;
  content_type: string;
  size_bytes: number | null;
  created_at: string;
}

export interface Location {
  id: string;
  project_id: string;
  address: string;
  latitude: number | null;
  longitude: number | null;
  contact_name: string | null;
  contact_phone: string | null;
  scheduled_at: string | null;
  confirmed: boolean;
  photos: LocationPhoto[];
  created_at: string;
  updated_at: string;
}

export interface CreateLocationBody {
  address: string;
  latitude?: number | null;
  longitude?: number | null;
  contact_name?: string | null;
  contact_phone?: string | null;
  scheduled_at?: string | null;
}

export interface InitPhotoUploadBody {
  content_type: string;
  size_bytes: number;
}

export interface InitPhotoUploadResponse {
  upload_session_url: string;
  gcs_bucket: string;
  gcs_object_name: string;
}

export interface FinalisePhotoBody {
  gcs_bucket: string;
  gcs_object_name: string;
  content_type: string;
  size_bytes: number;
}
