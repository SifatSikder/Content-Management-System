export interface DriveConnection {
  google_email: string;
  scopes: string;
  connected_at: string;
}

export interface StartConnectResponse {
  url: string;
}

export interface AttachDriveBody {
  folder_id: string;
  folder_url?: string | null;
}

export interface ImportGdocBody {
  document: string;
}
