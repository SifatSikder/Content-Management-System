/**
 * GCS resumable-upload chunked PUT.
 *
 * After the backend mints a session URL, the browser PUTs chunks of the file
 * with `Content-Range: bytes <start>-<end>/<total>`. GCS responds with:
 *   - 308 Resume Incomplete during the upload (no body, may include Range header)
 *   - 200 OK or 201 Created on the final chunk
 *
 * On pause/cancel, the caller aborts the controller. To resume, restart from
 * the next byte after the last successful chunk (we don't query the session for
 * the saved offset — Phase 1 keeps it simple by re-uploading from the last
 * confirmed chunk boundary).
 */

export interface UploadProgress {
  uploaded: number;
  total: number;
}

export interface UploadOptions {
  sessionUrl: string;
  file: File;
  chunkSize?: number;
  onProgress?: (p: UploadProgress) => void;
  signal?: AbortSignal;
}

const DEFAULT_CHUNK = 8 * 1024 * 1024;

export class UploadAbortedError extends Error {
  constructor() {
    super("upload aborted");
    this.name = "UploadAbortedError";
  }
}

export async function performResumableUpload(opts: UploadOptions): Promise<void> {
  const { sessionUrl, file, signal } = opts;
  const chunkSize = opts.chunkSize ?? DEFAULT_CHUNK;
  const total = file.size;
  let offset = 0;

  while (offset < total) {
    if (signal?.aborted) throw new UploadAbortedError();
    const end = Math.min(offset + chunkSize, total);
    const blob = file.slice(offset, end);
    const headers: Record<string, string> = {
      "Content-Length": String(end - offset),
      "Content-Range": `bytes ${offset}-${end - 1}/${total}`,
    };

    const response = await fetch(sessionUrl, {
      method: "PUT",
      headers,
      body: blob,
      signal,
    });

    if (response.status === 200 || response.status === 201) {
      offset = total;
      opts.onProgress?.({ uploaded: total, total });
      return;
    }
    if (response.status === 308) {
      // Resume-incomplete; advance.
      offset = end;
      opts.onProgress?.({ uploaded: offset, total });
      continue;
    }
    throw new Error(`Upload failed: HTTP ${response.status}`);
  }
}
