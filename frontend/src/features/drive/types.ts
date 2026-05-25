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

/** One row in the Drive picker — mirror of `app/schemas/drive.py::DriveDocumentPublic`. */
export interface DriveDocument {
  id: string;
  name: string;
  modified_time: string | null;
  web_view_link: string | null;
}

export interface DriveDocumentListResponse {
  items: DriveDocument[];
}

/** Rendered HTML body of a single Doc — non-persisting fetch result. */
export interface DriveDocumentContent {
  body: string;
}
