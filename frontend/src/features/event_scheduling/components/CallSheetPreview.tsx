"use client";

import { FileText } from "lucide-react";
import { useEffect, useState } from "react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { getCallSheetUrl } from "@/features/event_scheduling/api";

interface Props {
  shootId: string;
  shootLabel: string;
}

/**
 * Click-to-preview tile for a shoot's uploaded call-sheet PDF.
 * Lazy-fetches the signed URL on mount, re-wraps the bytes in a
 * Blob with `application/pdf` MIME so Chrome's iframe renders it
 * inline (resumable uploads land with unreliable Content-Type).
 * Mirrors `ReleaseThumbnail` in the casting feature.
 */
export function CallSheetPreview({ shootId, shootLabel }: Props) {
  const [open, setOpen] = useState(false);
  const [url, setUrl] = useState<string | null>(null);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [errored, setErrored] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let created: string | null = null;
    (async () => {
      try {
        const res = await getCallSheetUrl(shootId);
        if (cancelled) return;
        setUrl(res.url);
        const resp = await fetch(res.url);
        if (!resp.ok) throw new Error("fetch failed");
        const bytes = await resp.blob();
        const retyped = new Blob([bytes], { type: "application/pdf" });
        created = URL.createObjectURL(retyped);
        if (cancelled) {
          URL.revokeObjectURL(created);
          return;
        }
        setBlobUrl(created);
      } catch {
        if (!cancelled) setErrored(true);
      }
    })();
    return () => {
      cancelled = true;
      if (created) URL.revokeObjectURL(created);
    };
  }, [shootId]);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <button
          type="button"
          className="bg-muted hover:bg-muted/70 hover:ring-ring/40 group relative h-20 w-16 shrink-0 overflow-hidden rounded border transition-all hover:ring-2"
          aria-label="Open call sheet preview"
        >
          {errored ? (
            <div className="text-muted-foreground flex h-full items-center justify-center text-[10px]">
              ⚠
            </div>
          ) : (
            <div className="text-muted-foreground flex h-full flex-col items-center justify-center gap-1">
              <FileText className="size-6" />
              <span className="text-[9px] font-medium">PDF</span>
            </div>
          )}
        </button>
      </DialogTrigger>
      <DialogContent className="!max-w-[min(96vw,1400px)] sm:!max-w-[min(96vw,1400px)]">
        <DialogHeader>
          <DialogTitle>Call sheet — {shootLabel}</DialogTitle>
          <DialogDescription className="sr-only">
            Call sheet PDF for {shootLabel}
          </DialogDescription>
        </DialogHeader>
        {url && !errored ? (
          <iframe
            src={blobUrl ?? url}
            title={shootLabel}
            className="bg-muted h-[85vh] w-full rounded border"
          />
        ) : (
          <p className="text-muted-foreground p-6 text-sm">Loading…</p>
        )}
      </DialogContent>
    </Dialog>
  );
}
