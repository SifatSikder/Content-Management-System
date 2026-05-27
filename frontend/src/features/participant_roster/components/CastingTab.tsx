"use client";

import { FileText, ImageIcon, Trash2, Upload } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  createCast,
  deleteCast,
  finaliseRelease,
  getReleaseUrl,
  initReleaseUpload,
  listCast,
} from "@/features/participant_roster/api";
import { LockCastingButton } from "@/features/participant_roster/components/LockCastingButton";
import type { CastMember } from "@/features/participant_roster/types";
import { performResumableUpload } from "@/features/asset_review_with_timecodes/lib/resumable-upload";
import { getProject } from "@/features/projects/api";
import type { Project } from "@/features/projects/types";
import { ApiError } from "@/lib/api-client";

const RELEASE_ACCEPT = "application/pdf,image/jpeg,image/png,image/webp";
const RELEASE_MAX_BYTES = 25 * 1024 * 1024;

interface Props {
  project: Project;
  isOwner?: boolean;
  canInput?: boolean;
  onProjectUpdated?: (p: Project) => void;
}

export function CastingTab({
  project,
  isOwner = false,
  onProjectUpdated,
}: Props) {
  // Casting is owner-only — Asst CEO drives this; CEO + Director see
  // read-only. Mirrors how Idea + Script gate writes on `isOwner`
  // rather than the broader stage-assignee gate. Locking the casting
  // also freezes all writes (no new cast, no confirm toggle, no
  // delete, no release upload) until the owner unlocks via the Lock
  // button area; mirrors the Lock Idea/Lock Script lock-down.
  const castingLocked = project.casting_locked_at !== null;
  const canWrite = isOwner && !castingLocked;

  async function refreshProject() {
    try {
      const next = await getProject(project.id);
      onProjectUpdated?.(next);
    } catch {
      // Non-fatal — the stage chip will refresh on next nav.
    }
  }
  const t = useTranslations("casting");
  const tCommon = useTranslations("common");
  const tErr = useTranslations("errors");

  const [cast, setCast] = useState<CastMember[] | null>(null);
  const [creating, setCreating] = useState(false);
  const [draft, setDraft] = useState({
    name: "",
    role_description: "",
    contact_email: "",
    contact_phone: "",
  });

  const reload = useCallback(async () => {
    try {
      setCast(await listCast(project.id));
    } catch {
      toast.error(tErr("generic"));
    }
  }, [project.id, tErr]);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!draft.name.trim()) return;
    setCreating(true);
    try {
      await createCast(project.id, {
        name: draft.name.trim(),
        role_description: draft.role_description.trim() || null,
        contact_email: draft.contact_email.trim() || null,
        contact_phone: draft.contact_phone.trim() || null,
      });
      setDraft({ name: "", role_description: "", contact_email: "", contact_phone: "" });
      toast.success(t("created"));
      await reload();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : tErr("generic");
      toast.error(msg);
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-end">
        <LockCastingButton
          project={project}
          isOwner={isOwner}
          onLocked={() => void refreshProject()}
        />
      </div>
      {canWrite && (
      <Card className="p-4">
        <form className="space-y-3" onSubmit={onCreate}>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="cast-name">{t("name")}</Label>
              <Input
                id="cast-name"
                value={draft.name}
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="cast-email">{t("email")}</Label>
              <Input
                id="cast-email"
                type="email"
                value={draft.contact_email}
                onChange={(e) => setDraft({ ...draft, contact_email: e.target.value })}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="cast-phone">{t("phone")}</Label>
              <Input
                id="cast-phone"
                type="tel"
                value={draft.contact_phone}
                onChange={(e) => setDraft({ ...draft, contact_phone: e.target.value })}
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="cast-role">{t("role_description")}</Label>
            <Textarea
              id="cast-role"
              rows={2}
              value={draft.role_description}
              onChange={(e) => setDraft({ ...draft, role_description: e.target.value })}
              placeholder={t("role_placeholder")}
            />
          </div>
          <Button type="submit" size="sm" disabled={creating || !draft.name.trim()}>
            {creating ? tCommon("loading") : t("add")}
          </Button>
        </form>
      </Card>
      )}

      {cast === null ? (
        <p className="text-muted-foreground text-sm">{tCommon("loading")}</p>
      ) : cast.length === 0 ? (
        <p className="text-muted-foreground text-sm">{t("empty")}</p>
      ) : (
        <div className="space-y-3">
          {cast.map((c) => (
            <CastRow
              key={c.id}
              cast={c}
              canWrite={canWrite}
              onChanged={reload}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function CastRow({
  cast,
  canWrite,
  onChanged,
}: {
  cast: CastMember;
  canWrite: boolean;
  onChanged: () => void;
}) {
  const t = useTranslations("casting");
  const tCommon = useTranslations("common");
  const tErr = useTranslations("errors");
  const fileInput = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);

  async function onDelete() {
    setBusy(true);
    try {
      await deleteCast(cast.id);
      onChanged();
    } catch {
      toast.error(tErr("generic"));
    } finally {
      setBusy(false);
    }
  }

  async function onUploadRelease(file: File) {
    if (file.size > RELEASE_MAX_BYTES) {
      toast.error(t("release_too_large"));
      return;
    }
    setBusy(true);
    try {
      const init = await initReleaseUpload(cast.id, {
        content_type: file.type,
        size_bytes: file.size,
      });
      await performResumableUpload({ sessionUrl: init.upload_session_url, file });
      await finaliseRelease(cast.id, {
        gcs_bucket: init.gcs_bucket,
        gcs_object_name: init.gcs_object_name,
        content_type: file.type,
        size_bytes: file.size,
      });
      toast.success(t("release_uploaded"));
      onChanged();
    } catch {
      toast.error(tErr("generic"));
    } finally {
      setBusy(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  return (
    <Card className="space-y-3 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <span className="text-sm font-medium">{cast.name}</span>
          {cast.role_description && (
            <p className="text-muted-foreground text-xs">{cast.role_description}</p>
          )}
          {(cast.contact_email || cast.contact_phone) && (
            <p className="text-muted-foreground text-xs">
              {[cast.contact_email, cast.contact_phone].filter(Boolean).join(" · ")}
            </p>
          )}
        </div>
        {canWrite ? (
          <ConfirmDialog
            title={t("delete_confirm")}
            confirmLabel={tCommon("delete")}
            onConfirm={onDelete}
          >
            <Button
              variant="ghost"
              size="icon"
              disabled={busy}
              aria-label={tCommon("delete")}
            >
              <Trash2 className="size-4" />
            </Button>
          </ConfirmDialog>
        ) : null}
      </div>

      <div className="flex items-end gap-3">
        {cast.release_form_object_name && (
          <ReleaseThumbnail castId={cast.id} castName={cast.name} />
        )}
        {canWrite ? (
          <>
            <input
              ref={fileInput}
              type="file"
              accept={RELEASE_ACCEPT}
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) void onUploadRelease(f);
              }}
            />
            <Button
              variant="outline"
              size="sm"
              onClick={() => fileInput.current?.click()}
              disabled={busy}
            >
              <Upload className="mr-1.5 size-4" />
              {cast.release_form_object_name ? t("replace_release") : t("upload_release")}
            </Button>
          </>
        ) : null}
      </div>
    </Card>
  );
}

function ReleaseThumbnail({ castId, castName }: { castId: string; castName: string }) {
  const t = useTranslations("casting");
  const tCommon = useTranslations("common");
  const [open, setOpen] = useState(false);
  const [info, setInfo] = useState<{
    url: string; // direct signed URL — for <img>
    blobUrl: string | null; // typed-blob URL — used for PDF iframe to force correct MIME
    contentType: string;
  } | null>(null);
  const [errored, setErrored] = useState(false);

  // Lazy-load the signed URL on mount. For PDFs we also fetch the bytes and
  // re-wrap them in a Blob with the correct MIME so Chrome's iframe will
  // render inline — resumable uploads land with unreliable Content-Type, so
  // forcing the MIME client-side is the cleanest fix.
  useEffect(() => {
    let cancelled = false;
    let createdBlobUrl: string | null = null;
    (async () => {
      try {
        const res = await getReleaseUrl(castId);
        if (cancelled) return;
        let blobUrl: string | null = null;
        if (res.content_type === "application/pdf") {
          const resp = await fetch(res.url);
          if (!resp.ok) throw new Error("fetch failed");
          const bytes = await resp.blob();
          const retyped = new Blob([bytes], { type: "application/pdf" });
          blobUrl = URL.createObjectURL(retyped);
          createdBlobUrl = blobUrl;
        }
        if (cancelled) {
          if (blobUrl) URL.revokeObjectURL(blobUrl);
          return;
        }
        setInfo({ url: res.url, blobUrl, contentType: res.content_type });
      } catch {
        if (!cancelled) setErrored(true);
      }
    })();
    return () => {
      cancelled = true;
      if (createdBlobUrl) URL.revokeObjectURL(createdBlobUrl);
    };
  }, [castId]);

  const isPdf = info?.contentType === "application/pdf";
  const isImage = info?.contentType.startsWith("image/") ?? false;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <button
          type="button"
          className="bg-muted hover:bg-muted/70 hover:ring-ring/40 group relative h-20 w-16 shrink-0 overflow-hidden rounded border transition-all hover:ring-2"
          aria-label={t("release_open_preview")}
        >
          {errored ? (
            <div className="text-muted-foreground flex h-full items-center justify-center text-[10px]">
              ⚠
            </div>
          ) : info === null ? (
            <div className="bg-muted-foreground/10 size-full animate-pulse" />
          ) : isImage ? (
            <>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={info.url}
                alt={castName}
                className="size-full object-cover"
                onError={() => setErrored(true)}
              />
              <div className="bg-background/90 absolute right-1 bottom-1 flex items-center gap-0.5 rounded px-1 text-[9px] font-medium">
                <ImageIcon className="size-2.5" />
                IMG
              </div>
            </>
          ) : isPdf ? (
            // Static branded tile — real first-page rendering requires
            // pdfjs-dist (~1.2 MB) which isn't worth it for a 6-user tool.
            // The preview Dialog below renders the full PDF via iframe.
            <div className="text-muted-foreground flex h-full flex-col items-center justify-center gap-1">
              <FileText className="size-6" />
              <span className="text-[9px] font-medium">PDF</span>
            </div>
          ) : (
            <div className="text-muted-foreground flex h-full items-center justify-center text-[10px]">
              ?
            </div>
          )}
        </button>
      </DialogTrigger>
      <DialogContent className="!max-w-[min(96vw,1400px)] sm:!max-w-[min(96vw,1400px)]">
        <DialogHeader>
          <DialogTitle>
            {t("release_preview_title", { name: castName })}
          </DialogTitle>
          {/* sr-only description satisfies Radix's a11y requirement and tells
              screen-reader users what the modal contains. */}
          <DialogDescription className="sr-only">
            {t("release_preview_title", { name: castName })}
          </DialogDescription>
        </DialogHeader>
        {info && !errored ? (
          isPdf ? (
            <iframe
              src={info.blobUrl ?? info.url}
              title={castName}
              className="bg-muted h-[85vh] w-full rounded border"
            />
          ) : isImage ? (
            <div className="flex justify-center">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={info.url}
                alt={castName}
                className="max-h-[85vh] max-w-full rounded"
              />
            </div>
          ) : (
            <a
              href={info.url}
              target="_blank"
              rel="noreferrer"
              className="text-sm underline"
            >
              {tCommon("open")}
            </a>
          )
        ) : (
          <p className="text-muted-foreground p-6 text-sm">{tCommon("loading")}</p>
        )}
      </DialogContent>
    </Dialog>
  );
}
