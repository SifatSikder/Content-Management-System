"use client";

import { Upload } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { performResumableUpload } from "@/features/asset_review_with_timecodes/lib/resumable-upload";
import { useCanIDo } from "@/features/permissions/hooks/usePermissions";
import { apiFetchAuthed, ApiError } from "@/lib/api-client";
import type { Project } from "@/features/projects/types";

interface InitResponse {
  upload_session_url: string;
  gcs_bucket: string;
  gcs_object_name: string;
  chunk_size_bytes: number;
}

const ALLOWED = ["video/mp4", "video/quicktime", "video/x-msvideo"];
const ACCEPT = ".mp4,.mov,.avi,video/*";

interface Props {
  project: Project;
  shootId: string;
  onSubmitted?: () => void;
}

/**
 * "Submit raw cuts" CTA rendered per-shoot inside a wrapped ShootRow.
 * Streams a file straight to GCS via the resumable-upload helper, then
 * finalises through the FastAPI route which advances the project to
 * `editing` on the first submission for the project.
 */
export function SubmitRawCutCTA({ project, shootId, onSubmitted }: Props) {
  const canSubmit = useCanIDo(project.department_id, "raw_cut.submit");
  const [progress, setProgress] = useState<{ uploaded: number; total: number } | null>(
    null,
  );
  const inputRef = useRef<HTMLInputElement | null>(null);

  if (!canSubmit) return null;
  if (project.stage_key !== "shooting" && project.stage_key !== "editing")
    return null;

  async function handleFile(file: File) {
    const contentType = file.type || "application/octet-stream";
    if (!ALLOWED.includes(contentType)) {
      toast.error(`Unsupported file type: ${contentType}`);
      return;
    }
    setProgress({ uploaded: 0, total: file.size });
    try {
      const init = await apiFetchAuthed<InitResponse>(
        `/projects/${project.id}/raw-cuts/init-upload`,
        {
          method: "POST",
          body: {
            shoot_id: shootId,
            content_type: contentType,
            size_bytes: file.size,
            filename: file.name,
          } as unknown as BodyInit,
        },
      );

      await performResumableUpload({
        sessionUrl: init.upload_session_url,
        file,
        chunkSize: init.chunk_size_bytes,
        onProgress: (p) => setProgress(p),
      });

      await apiFetchAuthed(`/projects/${project.id}/raw-cuts`, {
        method: "POST",
        body: {
          shoot_id: shootId,
          gcs_bucket: init.gcs_bucket,
          gcs_object_name: init.gcs_object_name,
          content_type: contentType,
          size_bytes: file.size,
          original_filename: file.name,
        } as unknown as BodyInit,
      });

      toast.success("Raw cut submitted — project advanced to Editing");
      onSubmitted?.();
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : "Raw cut submission failed";
      toast.error(msg);
    } finally {
      setProgress(null);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <div className="space-y-2">
      <Button
        onClick={() => inputRef.current?.click()}
        disabled={progress !== null}
      >
        <Upload className="size-4" />
        {progress === null ? "Submit raw cuts" : "Uploading…"}
      </Button>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) void handleFile(f);
        }}
      />
      {progress !== null ? (
        <div className="space-y-1">
          <Progress
            value={
              progress.total > 0 ? (progress.uploaded / progress.total) * 100 : 0
            }
          />
          <div className="text-muted-foreground text-[11px]">
            {Math.round((progress.uploaded / 1024 / 1024) * 10) / 10} /{" "}
            {Math.round((progress.total / 1024 / 1024) * 10) / 10} MB
          </div>
        </div>
      ) : null}
    </div>
  );
}
