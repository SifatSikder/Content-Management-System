"use client";

import { Upload, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Textarea } from "@/components/ui/textarea";
import { finaliseEdit, initUpload, listEditComments } from "@/features/edits/api";
import {
  UploadAbortedError,
  performResumableUpload,
} from "@/features/edits/lib/resumable-upload";
import type { EditComment, EditVersion } from "@/features/edits/types";

const ACCEPT_TYPES = ["video/mp4", "video/quicktime"];
const MAX_SIZE = 2 * 1024 * 1024 * 1024;

interface Props {
  projectId: string;
  previousVersion: EditVersion | null;
  onUploaded: (edit: EditVersion) => void;
  trigger: React.ReactNode;
}

function formatMb(bytes: number): string {
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function UploadDialog({ projectId, previousVersion, onUploaded, trigger }: Props) {
  const t = useTranslations("edits");
  const tCommon = useTranslations("common");
  const tToast = useTranslations("toast");
  const tErr = useTranslations("errors");
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [notes, setNotes] = useState("");
  const [prevComments, setPrevComments] = useState<EditComment[]>([]);
  const [resolved, setResolved] = useState<Set<string>>(new Set());
  const [progress, setProgress] = useState(0);
  const [phase, setPhase] = useState<"idle" | "uploading" | "finalising">("idle");
  const abortRef = useRef<AbortController | null>(null);

  // Load previous version's open comments for the V2 checklist.
  useEffect(() => {
    if (!open || !previousVersion) {
      setPrevComments([]);
      return;
    }
    let cancelled = false;
    void listEditComments(previousVersion.id).then((list) => {
      if (cancelled) return;
      setPrevComments(list.filter((c) => !c.resolved_at));
    });
    return () => {
      cancelled = true;
    };
  }, [open, previousVersion]);

  const canSubmit = useMemo(
    () => file !== null && phase === "idle",
    [file, phase],
  );

  const toggleResolved = useCallback((id: string) => {
    setResolved((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  function reset() {
    setFile(null);
    setNotes("");
    setResolved(new Set());
    setProgress(0);
    setPhase("idle");
    abortRef.current = null;
  }

  async function onPick(f: File) {
    if (!ACCEPT_TYPES.includes(f.type)) {
      toast.error(`${tErr("validation")}: ${f.type}`);
      return;
    }
    if (f.size > MAX_SIZE) {
      toast.error(`${t("size_cap")}: ${formatMb(f.size)}`);
      return;
    }
    setFile(f);
  }

  async function startUpload() {
    if (!file) return;
    setPhase("uploading");
    setProgress(0);
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const init = await initUpload(projectId, {
        content_type: file.type,
        size_bytes: file.size,
        filename: file.name,
      });

      await performResumableUpload({
        sessionUrl: init.upload_session_url,
        file,
        chunkSize: init.chunk_size_bytes,
        signal: controller.signal,
        onProgress: ({ uploaded, total }) =>
          setProgress(Math.round((uploaded / total) * 100)),
      });

      setPhase("finalising");
      const edit = await finaliseEdit(projectId, {
        gcs_bucket: init.gcs_bucket,
        gcs_object_name: init.gcs_object_name,
        content_type: file.type,
        size_bytes: file.size,
        notes: notes || null,
        resolved_comments: Array.from(resolved),
      });
      toast.success(tToast("edit_uploaded"));
      onUploaded(edit);
      setOpen(false);
      reset();
    } catch (err) {
      if (err instanceof UploadAbortedError) {
        toast.message(tCommon("cancel"));
      } else {
        toast.error(t("upload_failed"));
      }
      setPhase("idle");
    }
  }

  function cancel() {
    abortRef.current?.abort();
    setPhase("idle");
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o && phase !== "idle") return; // don't close mid-upload
        if (!o) reset();
        setOpen(o);
      }}
    >
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t("upload_cv")}</DialogTitle>
          <DialogDescription>{t("size_cap")}</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {!file ? (
            <Label
              htmlFor="edit-file-input"
              className="border-muted-foreground/30 hover:bg-muted/40 flex cursor-pointer flex-col items-center gap-2 rounded-md border-2 border-dashed p-8 text-center text-sm"
            >
              <Upload className="size-6" />
              {t("drag_or_choose")}
              <input
                id="edit-file-input"
                type="file"
                accept={ACCEPT_TYPES.join(",")}
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) void onPick(f);
                }}
              />
            </Label>
          ) : (
            <div className="bg-muted/30 flex items-center justify-between rounded-md border p-3 text-sm">
              <div>
                <div className="font-medium">{file.name}</div>
                <div className="text-muted-foreground text-xs">{formatMb(file.size)}</div>
              </div>
              {phase === "idle" && (
                <Button variant="ghost" size="sm" onClick={() => setFile(null)}>
                  <X className="size-4" />
                </Button>
              )}
            </div>
          )}

          {previousVersion && prevComments.length > 0 && phase === "idle" && (
            <div className="space-y-2">
              <Label className="text-muted-foreground text-xs">
                {t("resolved_v1_label")}
              </Label>
              <ul className="space-y-1 rounded-md border p-2">
                {prevComments.map((c) => (
                  <li key={c.id} className="flex items-start gap-2 text-sm">
                    <Checkbox
                      id={`rc-${c.id}`}
                      checked={resolved.has(c.id)}
                      onCheckedChange={() => toggleResolved(c.id)}
                    />
                    <label htmlFor={`rc-${c.id}`} className="cursor-pointer">
                      <span className="text-muted-foreground mr-2 text-xs">
                        @{c.timestamp_seconds.toFixed(1)}s
                      </span>
                      {c.body}
                    </label>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {file && phase === "idle" && (
            <Textarea
              rows={2}
              placeholder={t("notes_placeholder")}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          )}

          {phase !== "idle" && (
            <div className="space-y-2">
              <Progress value={progress} />
              <p className="text-muted-foreground text-xs">
                {phase === "uploading" ? `${t("uploading")} ${progress}%` : tCommon("loading")}
              </p>
            </div>
          )}
        </div>

        <DialogFooter>
          {phase === "idle" ? (
            <>
              <Button variant="outline" onClick={() => setOpen(false)}>
                {tCommon("cancel")}
              </Button>
              <Button onClick={startUpload} disabled={!canSubmit}>
                {t("upload_cv")}
              </Button>
            </>
          ) : (
            <Button variant="destructive" onClick={cancel}>
              {tCommon("cancel")}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
