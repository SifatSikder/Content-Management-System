"use client";

import { Calendar, Play, Square, Trash2, Upload } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { performResumableUpload } from "@/features/edits/lib/resumable-upload";
import type { Project } from "@/features/projects/types";
import {
  createShoot,
  deleteShoot,
  finaliseCallSheet,
  initCallSheetUpload,
  listShoots,
  startShoot,
  updateShoot,
  wrapShoot,
} from "@/features/shoots/api";
import type { Shoot, ShootStatus } from "@/features/shoots/types";
import { ApiError } from "@/lib/api-client";

const CALL_SHEET_MAX_BYTES = 25 * 1024 * 1024;

interface Props {
  project: Project;
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

export function ShootTab({ project }: Props) {
  const t = useTranslations("shoots");
  const tCommon = useTranslations("common");
  const tErr = useTranslations("errors");

  const [shoots, setShoots] = useState<Shoot[] | null>(null);
  const [creating, setCreating] = useState(false);
  const [scheduledAt, setScheduledAt] = useState("");
  const [gearText, setGearText] = useState("");

  const reload = useCallback(async () => {
    try {
      setShoots(await listShoots(project.id));
    } catch {
      toast.error(tErr("generic"));
    }
  }, [project.id, tErr]);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    try {
      const gear: Record<string, boolean> = {};
      for (const raw of gearText.split("\n")) {
        const item = raw.trim();
        if (item) gear[item] = false;
      }
      await createShoot(project.id, {
        scheduled_at: parseDateTimeLocal(scheduledAt),
        gear_checklist: gear,
      });
      setScheduledAt("");
      setGearText("");
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
          <div className="space-y-1.5">
            <Label htmlFor="shoot-gear">{t("gear_checklist")}</Label>
            <Textarea
              id="shoot-gear"
              rows={4}
              value={gearText}
              onChange={(e) => setGearText(e.target.value)}
              placeholder={t("gear_placeholder")}
            />
            <p className="text-muted-foreground text-xs">{t("gear_hint")}</p>
          </div>
          <Button type="submit" size="sm" disabled={creating}>
            {creating ? tCommon("loading") : t("add")}
          </Button>
        </form>
      </Card>

      {shoots === null ? (
        <p className="text-muted-foreground text-sm">{tCommon("loading")}</p>
      ) : shoots.length === 0 ? (
        <p className="text-muted-foreground text-sm">{t("empty")}</p>
      ) : (
        <div className="space-y-3">
          {shoots.map((s) => (
            <ShootRow key={s.id} shoot={s} onChanged={reload} />
          ))}
        </div>
      )}
    </div>
  );
}

function ShootRow({ shoot, onChanged }: { shoot: Shoot; onChanged: () => void }) {
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

  const gearEntries = Object.entries(shoot.gear_checklist ?? {});
  const formatted =
    shoot.scheduled_at !== null
      ? new Date(shoot.scheduled_at).toLocaleString(undefined, {
          dateStyle: "medium",
          timeStyle: "short",
        })
      : t("no_date");

  async function toggleGear(item: string, value: boolean) {
    const next = { ...shoot.gear_checklist, [item]: value };
    await action(() => updateShoot(shoot.id, { gear_checklist: next }));
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
              onClick={() => action(() => wrapShoot(shoot.id), "wrapped_toast")}
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
      </div>

      {gearEntries.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-muted-foreground text-xs font-medium uppercase tracking-wider">
            {t("gear_checklist")}
          </p>
          <div className="grid grid-cols-1 gap-1.5 md:grid-cols-2">
            {gearEntries.map(([item, value]) => (
              <label key={item} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={Boolean(value)}
                  onChange={(e) => toggleGear(item, e.target.checked)}
                  disabled={busy || shoot.status === "wrapped"}
                  className="size-4 rounded border-input"
                />
                <span className={value ? "text-muted-foreground line-through" : ""}>{item}</span>
              </label>
            ))}
          </div>
        </div>
      )}

      <div>
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
          {shoot.call_sheet_object_name ? t("replace_call_sheet") : t("upload_call_sheet")}
        </Button>
      </div>
    </Card>
  );
}
