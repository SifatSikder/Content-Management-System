"use client";

import { Calendar, Play, Square, Trash2, Upload } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { useSession } from "next-auth/react";

import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { performResumableUpload } from "@/features/asset_review_with_timecodes/lib/resumable-upload";
import { SubmitRawCutCTA } from "@/features/asset_review_with_timecodes/components/SubmitRawCutCTA";
import { CallSheetPreview } from "@/features/event_scheduling/components/CallSheetPreview";
import { getProject, listStageAssignees } from "@/features/projects/api";
import type { Project } from "@/features/projects/types";
import {
  createShoot,
  deleteShoot,
  finaliseCallSheet,
  initCallSheetUpload,
  listRawCuts,
  listShoots,
  startShoot,
  updateShoot,
  wrapShoot,
} from "@/features/event_scheduling/api";
import type {
  RawCutSubmission,
  Shoot,
  ShootStatus,
} from "@/features/event_scheduling/types";
import { ApiError } from "@/lib/api-client";

const CALL_SHEET_MAX_BYTES = 25 * 1024 * 1024;

interface Props {
  project: Project;
  canInput?: boolean;
  onProjectUpdated?: (next: Project) => void;
}

function statusBadgeVariant(s: ShootStatus): "default" | "secondary" | "outline" {
  if (s === "in_progress") return "default";
  if (s === "wrapped") return "secondary";
  return "outline";
}

function formatDateTimeLocal(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function parseDateTimeLocal(value: string): string | null {
  if (!value) return null;
  return new Date(value).toISOString();
}

export function ShootTab({ project, onProjectUpdated }: Props) {
  const t = useTranslations("shoots");
  const tCommon = useTranslations("common");
  const tErr = useTranslations("errors");
  const { data: session } = useSession();
  const currentUserId =
    (session?.user as { id?: string } | undefined)?.id ?? "";

  const [shoots, setShoots] = useState<Shoot[] | null>(null);
  const [rawCuts, setRawCuts] = useState<RawCutSubmission[]>([]);
  const [creating, setCreating] = useState(false);
  const [scheduledAt, setScheduledAt] = useState("");
  // Shoot management is Director-only — gated on active stage
  // assignment, not on `canInput`. Owner (Asst CEO) + CEO see the tab
  // read-only so they can monitor progress without touching anything.
  const [canWrite, setCanWrite] = useState(false);

  const reload = useCallback(async () => {
    try {
      const [s, rc] = await Promise.all([
        listShoots(project.id),
        listRawCuts(project.id).catch(() => [] as RawCutSubmission[]),
      ]);
      setShoots(s);
      setRawCuts(rc);
    } catch {
      toast.error(tErr("generic"));
    }
  }, [project.id, tErr]);

  useEffect(() => {
    void reload();
  }, [reload]);

  useEffect(() => {
    let cancelled = false;
    if (!currentUserId) {
      setCanWrite(false);
      return;
    }
    (async () => {
      try {
        const res = await listStageAssignees(project.id, "shooting");
        if (cancelled) return;
        // listStageAssignees already filters server-side to active rows.
        setCanWrite(res.items.some((a) => a.user_id === currentUserId));
      } catch {
        if (cancelled) return;
        setCanWrite(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [project.id, currentUserId]);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    try {
      await createShoot(project.id, {
        scheduled_at: parseDateTimeLocal(scheduledAt),
      });
      setScheduledAt("");
      toast.success(t("created"));
      await reload();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : tErr("generic");
      toast.error(msg);
    } finally {
      setCreating(false);
    }
  }

  function onShootWrapped() {
    toast.success(t("wrapped_prompt_upload"));
  }

  // Pre-compute per-shoot raw cuts so each row reads from local memory.
  const cutsByShoot = new Map<string, RawCutSubmission[]>();
  for (const cut of rawCuts) {
    if (cut.shoot_id === null) continue;
    const list = cutsByShoot.get(cut.shoot_id) ?? [];
    list.push(cut);
    cutsByShoot.set(cut.shoot_id, list);
  }

  async function refreshProject() {
    if (!onProjectUpdated) return;
    try {
      const next = await getProject(project.id);
      onProjectUpdated(next);
    } catch {
      // non-fatal — page chip will catch up on next nav
    }
  }

  return (
    <div className="space-y-4">
      {canWrite && (
      <Card className="p-4">
        <form className="space-y-3" onSubmit={onCreate}>
          <div className="space-y-1.5">
            <Label htmlFor="shoot-scheduled">{t("scheduled_at")}</Label>
            <Input
              id="shoot-scheduled"
              type="datetime-local"
              value={scheduledAt}
              onChange={(e) => setScheduledAt(e.target.value)}
            />
          </div>
          <Button type="submit" size="sm" disabled={creating}>
            {creating ? tCommon("loading") : t("add")}
          </Button>
        </form>
      </Card>
      )}

      {shoots === null ? (
        <p className="text-muted-foreground text-sm">{tCommon("loading")}</p>
      ) : shoots.length === 0 ? (
        <p className="text-muted-foreground text-sm">{t("empty")}</p>
      ) : (
        <div className="space-y-3">
          {shoots.map((s) => (
            <ShootRow
              key={s.id}
              project={project}
              shoot={s}
              rawCuts={cutsByShoot.get(s.id) ?? []}
              canWrite={canWrite}
              onChanged={reload}
              onWrapped={onShootWrapped}
              onProjectStageMayChange={refreshProject}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function formatBytes(bytes: number | null): string {
  if (bytes === null) return "";
  const mb = bytes / 1024 / 1024;
  if (mb < 1024) return `${mb.toFixed(1)} MB`;
  return `${(mb / 1024).toFixed(2)} GB`;
}

function ShootRow({
  project,
  shoot,
  rawCuts,
  canWrite,
  onChanged,
  onWrapped,
  onProjectStageMayChange,
}: {
  project: Project;
  shoot: Shoot;
  rawCuts: RawCutSubmission[];
  canWrite: boolean;
  onChanged: () => void;
  onWrapped?: () => void;
  onProjectStageMayChange?: () => Promise<void>;
}) {
  const t = useTranslations("shoots");
  const tCommon = useTranslations("common");
  const tErr = useTranslations("errors");
  const fileInput = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);

  async function action(fn: () => Promise<unknown>, successKey?: string) {
    setBusy(true);
    try {
      await fn();
      if (successKey) toast.success(t(successKey));
      onChanged();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : tErr("generic");
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  }

  async function onUploadCallSheet(file: File) {
    if (file.type !== "application/pdf") {
      toast.error(t("call_sheet_pdf_only"));
      return;
    }
    if (file.size > CALL_SHEET_MAX_BYTES) {
      toast.error(t("call_sheet_too_large"));
      return;
    }
    setBusy(true);
    try {
      const init = await initCallSheetUpload(shoot.id, {
        content_type: file.type,
        size_bytes: file.size,
      });
      await performResumableUpload({ sessionUrl: init.upload_session_url, file });
      await finaliseCallSheet(shoot.id, {
        gcs_bucket: init.gcs_bucket,
        gcs_object_name: init.gcs_object_name,
      });
      toast.success(t("call_sheet_uploaded"));
      onChanged();
    } catch {
      toast.error(tErr("generic"));
    } finally {
      setBusy(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  const formatted =
    shoot.scheduled_at !== null
      ? new Date(shoot.scheduled_at).toLocaleString(undefined, {
          dateStyle: "medium",
          timeStyle: "short",
        })
      : t("no_date");

  async function handleWrap() {
    setBusy(true);
    try {
      await wrapShoot(shoot.id);
      onChanged();
      onWrapped?.();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : tErr("generic");
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="space-y-3 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <Calendar className="text-muted-foreground size-3.5" />
            <span className="text-sm font-medium">{formatted}</span>
            <Badge variant={statusBadgeVariant(shoot.status)}>{t(`status.${shoot.status}`)}</Badge>
          </div>
          {shoot.started_at && (
            <p className="text-muted-foreground text-xs">
              {t("started_at", { time: new Date(shoot.started_at).toLocaleString() })}
            </p>
          )}
          {shoot.wrapped_at && (
            <p className="text-muted-foreground text-xs">
              {t("wrapped_at", { time: new Date(shoot.wrapped_at).toLocaleString() })}
            </p>
          )}
        </div>
        {canWrite ? (
          <div className="flex items-center gap-1">
            {shoot.status === "scheduled" && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => action(() => startShoot(shoot.id), "started_toast")}
                disabled={busy}
              >
                <Play className="mr-1.5 size-3.5" />
                {t("start")}
              </Button>
            )}
            {shoot.status === "in_progress" && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleWrap}
                disabled={busy}
              >
                <Square className="mr-1.5 size-3.5" />
                {t("wrap")}
              </Button>
            )}
            <ConfirmDialog
              title={t("delete_confirm")}
              confirmLabel={tCommon("delete")}
              onConfirm={() => action(() => deleteShoot(shoot.id))}
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
          </div>
        ) : null}
      </div>

      {shoot.call_sheet_object_name || canWrite ? (
        <div className="flex items-end gap-3">
          {shoot.call_sheet_object_name ? (
            <CallSheetPreview shootId={shoot.id} shootLabel={formatted} />
          ) : null}
          {canWrite ? (
            <>
              <input
                ref={fileInput}
                type="file"
                accept="application/pdf"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) void onUploadCallSheet(f);
                }}
              />
              <Button
                variant="outline"
                size="sm"
                onClick={() => fileInput.current?.click()}
                disabled={busy}
              >
                <Upload className="mr-1.5 size-4" />
                {shoot.call_sheet_object_name
                  ? t("replace_call_sheet")
                  : t("upload_call_sheet")}
              </Button>
            </>
          ) : null}
        </div>
      ) : null}

      {shoot.status === "wrapped" ? (
        <div className="space-y-2 border-t pt-3">
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            {t("raw_cuts_title")}
          </p>
          {rawCuts.length === 0 ? (
            <p className="text-muted-foreground text-xs">
              {t("raw_cuts_empty")}
            </p>
          ) : (
            <ul className="space-y-1">
              {rawCuts
                .slice()
                .sort((a, b) =>
                  a.submitted_at < b.submitted_at ? 1 : -1,
                )
                .map((rc) => (
                  <li
                    key={rc.id}
                    className="bg-muted/40 flex items-center justify-between gap-2 rounded-md px-2 py-1.5 text-xs"
                  >
                    <span className="truncate">
                      {rc.original_filename ?? rc.gcs_object_name}
                    </span>
                    <span className="text-muted-foreground shrink-0">
                      {formatBytes(rc.byte_size)}
                    </span>
                  </li>
                ))}
            </ul>
          )}
          {canWrite ? (
            <SubmitRawCutCTA
              project={project}
              shootId={shoot.id}
              onSubmitted={async () => {
                onChanged();
                await onProjectStageMayChange?.();
              }}
            />
          ) : null}
        </div>
      ) : null}
    </Card>
  );
}
