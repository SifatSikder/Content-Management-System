"use client";

import { Calendar, Download, Play } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import {
  getRawCutUrl,
  listRawCuts,
  listShoots,
} from "@/features/event_scheduling/api";
import type {
  RawCutSubmission,
  Shoot,
} from "@/features/event_scheduling/types";

interface Props {
  projectId: string;
}

function formatBytes(bytes: number | null): string {
  if (bytes === null) return "—";
  const mb = bytes / 1024 / 1024;
  if (mb < 1024) return `${mb.toFixed(1)} MB`;
  return `${(mb / 1024).toFixed(2)} GB`;
}

function formatDate(iso: string | null): string {
  if (!iso) return "Date TBD";
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function formatShortDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "short",
    timeStyle: "short",
  });
}

/**
 * Read-only roster of every raw cut uploaded for the project, grouped
 * by shoot and ordered by shoot date. Rendered on the Edits tab so the
 * editor can grab footage without bouncing to the Shoot tab. Each cut
 * has a one-click signed-URL download.
 */
export function RawCutsByShoot({ projectId }: Props) {
  const [shoots, setShoots] = useState<Shoot[] | null>(null);
  const [cuts, setCuts] = useState<RawCutSubmission[] | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [previewing, setPreviewing] = useState<string | null>(null);
  const [preview, setPreview] = useState<
    { cut: RawCutSubmission; url: string } | null
  >(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [s, rc] = await Promise.all([
          listShoots(projectId),
          listRawCuts(projectId).catch(() => [] as RawCutSubmission[]),
        ]);
        if (cancelled) return;
        setShoots(s);
        setCuts(rc);
      } catch {
        if (cancelled) return;
        setShoots([]);
        setCuts([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  async function handleDownload(cutId: string) {
    setDownloading(cutId);
    try {
      const res = await getRawCutUrl(projectId, cutId, "attachment");
      // Open in a new tab — Content-Disposition: attachment on the URL
      // makes the browser kick off a save rather than navigate.
      window.open(res.url, "_blank", "noopener");
    } catch {
      toast.error("Failed to get download link");
    } finally {
      setDownloading(null);
    }
  }

  async function handlePreview(cut: RawCutSubmission) {
    setPreviewing(cut.id);
    try {
      const res = await getRawCutUrl(projectId, cut.id, "inline");
      setPreview({ cut, url: res.url });
    } catch {
      toast.error("Failed to load preview");
    } finally {
      setPreviewing(null);
    }
  }

  if (shoots === null || cuts === null) {
    return <Skeleton className="h-32 w-full" />;
  }

  // Group raw cuts by shoot_id. Cuts with null shoot_id (legacy
  // pre-per-shoot data) end up in a separate "unsorted" bucket.
  const cutsByShoot = new Map<string, RawCutSubmission[]>();
  const orphanCuts: RawCutSubmission[] = [];
  for (const c of cuts) {
    if (c.shoot_id === null) {
      orphanCuts.push(c);
      continue;
    }
    const list = cutsByShoot.get(c.shoot_id) ?? [];
    list.push(c);
    cutsByShoot.set(c.shoot_id, list);
  }

  // Show every shoot, ordered by scheduled_at (nulls last). Empty
  // shoots still render so the editor sees the full picture.
  const orderedShoots = [...shoots].sort((a, b) => {
    if (a.scheduled_at && b.scheduled_at)
      return a.scheduled_at < b.scheduled_at ? -1 : 1;
    if (a.scheduled_at) return -1;
    if (b.scheduled_at) return 1;
    return a.created_at < b.created_at ? -1 : 1;
  });

  const totalCuts = cuts.length;

  if (totalCuts === 0 && orderedShoots.length === 0) {
    return null;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">
          Raw cuts
          <span className="text-muted-foreground ml-2 text-xs font-normal">
            {totalCuts} file{totalCuts === 1 ? "" : "s"} across {orderedShoots.length}{" "}
            shoot{orderedShoots.length === 1 ? "" : "s"}
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {orderedShoots.map((shoot) => {
          const shootCuts = (cutsByShoot.get(shoot.id) ?? []).slice().sort(
            (a, b) => (a.submitted_at < b.submitted_at ? -1 : 1),
          );
          return (
            <div key={shoot.id} className="space-y-2">
              <div className="flex items-center gap-2 text-sm font-medium">
                <Calendar className="text-muted-foreground size-3.5" />
                <span>{formatDate(shoot.scheduled_at)}</span>
                <span className="text-muted-foreground text-xs">
                  · {shootCuts.length} cut{shootCuts.length === 1 ? "" : "s"}
                </span>
              </div>
              {shootCuts.length === 0 ? (
                <p className="text-muted-foreground pl-5 text-xs">
                  No cuts uploaded for this shoot.
                </p>
              ) : (
                <ul className="divide-border ml-5 divide-y rounded-md border">
                  {shootCuts.map((cut) => (
                    <li
                      key={cut.id}
                      className="flex items-center justify-between gap-2 p-2 text-xs"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="truncate font-medium">
                          {cut.original_filename ?? cut.gcs_object_name}
                        </p>
                        <p className="text-muted-foreground">
                          {formatBytes(cut.byte_size)} · uploaded{" "}
                          {formatShortDate(cut.submitted_at)}
                        </p>
                      </div>
                      <div className="flex shrink-0 items-center gap-1">
                        <button
                          type="button"
                          onClick={() => void handlePreview(cut)}
                          disabled={previewing === cut.id}
                          className="hover:bg-muted text-muted-foreground hover:text-foreground inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs transition disabled:opacity-50"
                          title="Preview in browser"
                        >
                          <Play className="size-3" />
                          {previewing === cut.id ? "…" : "Preview"}
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleDownload(cut.id)}
                          disabled={downloading === cut.id}
                          className="hover:bg-muted text-muted-foreground hover:text-foreground inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs transition disabled:opacity-50"
                          title="Download raw cut"
                        >
                          <Download className="size-3" />
                          {downloading === cut.id ? "…" : "Download"}
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}
        <Dialog
          open={preview !== null}
          onOpenChange={(o) => {
            if (!o) setPreview(null);
          }}
        >
          <DialogContent className="!max-w-[min(96vw,1400px)] sm:!max-w-[min(96vw,1400px)]">
            <DialogHeader>
              <DialogTitle>
                {preview?.cut.original_filename ?? preview?.cut.gcs_object_name}
              </DialogTitle>
              <DialogDescription className="sr-only">
                Raw cut preview
              </DialogDescription>
            </DialogHeader>
            {preview ? (
              /* eslint-disable-next-line jsx-a11y/media-has-caption */
              <video
                key={preview.cut.id}
                src={preview.url}
                controls
                autoPlay
                className="bg-muted max-h-[80vh] w-full rounded border"
              />
            ) : null}
          </DialogContent>
        </Dialog>
        {orphanCuts.length > 0 ? (
          <div className="space-y-2 border-t pt-3">
            <p className="text-muted-foreground text-xs font-medium uppercase tracking-wider">
              Unsorted
            </p>
            <ul className="divide-border divide-y rounded-md border">
              {orphanCuts.map((cut) => (
                <li
                  key={cut.id}
                  className="flex items-center justify-between gap-2 p-2 text-xs"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium">
                      {cut.original_filename ?? cut.gcs_object_name}
                    </p>
                    <p className="text-muted-foreground">
                      {formatBytes(cut.byte_size)} · uploaded{" "}
                      {formatShortDate(cut.submitted_at)}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => void handleDownload(cut.id)}
                    disabled={downloading === cut.id}
                    className="hover:bg-muted text-muted-foreground hover:text-foreground inline-flex shrink-0 items-center gap-1 rounded-md border px-2 py-1 text-xs transition disabled:opacity-50"
                    title="Download raw cut"
                  >
                    <Download className="size-3" />
                    {downloading === cut.id ? "…" : "Download"}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
