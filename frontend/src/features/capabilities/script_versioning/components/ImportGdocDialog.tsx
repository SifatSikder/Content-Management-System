"use client";

import { Cloud, FileText, Loader2, Search } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import type { ScriptVersion } from "@/features/capabilities/script_versioning/types";
import {
  getDriveConnection,
  importGdoc,
  listDriveDocuments,
  startDriveConnect,
} from "@/features/drive/api";
import type { DriveDocument } from "@/features/drive/types";
import { ApiError } from "@/lib/api-client";

interface Props {
  projectId: string;
  onImported: (version: ScriptVersion) => void;
  trigger?: React.ReactNode;
  disabled?: boolean;
}

type Mode = "checking" | "disconnected" | "ready" | "error";

function formatDate(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString();
}

export function ImportGdocDialog({ projectId, onImported, trigger, disabled }: Props) {
  const t = useTranslations("script");
  const tDrive = useTranslations("drive");
  const tErr = useTranslations("errors");
  const tCommon = useTranslations("common");
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<Mode>("checking");
  const [docs, setDocs] = useState<DriveDocument[]>([]);
  const [query, setQuery] = useState("");
  const [listing, setListing] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [importingId, setImportingId] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setMode("checking");
    try {
      const conn = await getDriveConnection();
      if (!conn) {
        setMode("disconnected");
        return;
      }
      setMode("ready");
    } catch {
      setMode("error");
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    void reload();
  }, [open, reload]);

  // Debounced doc list fetch when in ready mode.
  useEffect(() => {
    if (mode !== "ready") return;
    let cancelled = false;
    setListing(true);
    const handle = setTimeout(async () => {
      try {
        const resp = await listDriveDocuments(query.trim() || undefined, 50);
        if (cancelled) return;
        setDocs(resp.items);
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 412) {
          // Stale credentials — fall back to disconnected and let user reconnect.
          setMode("disconnected");
        } else {
          setMode("error");
        }
      } finally {
        if (!cancelled) setListing(false);
      }
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(handle);
    };
  }, [mode, query]);

  async function startConnect() {
    setConnecting(true);
    try {
      const { url } = await startDriveConnect();
      window.location.href = url;
    } catch {
      toast.error(tDrive("connect_failed"));
      setConnecting(false);
    }
  }

  async function pick(doc: DriveDocument) {
    setImportingId(doc.id);
    try {
      const version = (await importGdoc(projectId, { document: doc.id })) as ScriptVersion;
      onImported(version);
      toast.success(t("import_succeeded"));
      setOpen(false);
      setQuery("");
    } catch (err) {
      if (err instanceof ApiError && err.status === 412) {
        toast.error(tDrive("disconnected"));
        setMode("disconnected");
      } else if (err instanceof ApiError && err.status === 403) {
        toast.error(t("import_forbidden"));
      } else if (err instanceof ApiError && err.status === 404) {
        toast.error(t("import_not_found"));
      } else {
        toast.error(tErr("generic"));
      }
    } finally {
      setImportingId(null);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger ?? (
          <Button size="sm" variant="outline" disabled={disabled}>
            <Cloud className="mr-2 size-4" />
            {t("import_from_drive")}
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t("import_dialog_title")}</DialogTitle>
          <DialogDescription>{t("import_picker_description")}</DialogDescription>
        </DialogHeader>

        {mode === "checking" && (
          <div className="space-y-2 py-2">
            {[...Array(4)].map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        )}

        {mode === "disconnected" && (
          <div className="space-y-4 py-2">
            <p className="text-muted-foreground text-sm">
              {t("import_connect_drive_hint")}
            </p>
            <Button onClick={startConnect} disabled={connecting} className="w-full">
              {connecting ? (
                <Loader2 className="mr-2 size-4 animate-spin" />
              ) : (
                <Cloud className="mr-2 size-4" />
              )}
              {tDrive("connect")}
            </Button>
          </div>
        )}

        {mode === "error" && (
          <div className="space-y-3 py-2">
            <p className="text-muted-foreground text-sm">{tErr("generic")}</p>
            <Button variant="outline" onClick={() => reload()}>
              {tCommon("retry")}
            </Button>
          </div>
        )}

        {mode === "ready" && (
          <div className="min-w-0 space-y-3">
            <div className="relative">
              <Search className="text-muted-foreground absolute top-1/2 left-2 size-4 -translate-y-1/2" />
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={t("import_search_placeholder")}
                className="pl-8"
                autoFocus
              />
            </div>
            <ScrollArea className="h-72 rounded-md border">
              {listing && docs.length === 0 ? (
                <div className="space-y-2 p-2">
                  {[...Array(5)].map((_, i) => (
                    <Skeleton key={i} className="h-10 w-full" />
                  ))}
                </div>
              ) : docs.length === 0 ? (
                <p className="text-muted-foreground p-6 text-center text-sm">
                  {query.trim() ? t("import_no_matches") : t("import_no_docs")}
                </p>
              ) : (
                <ul className="divide-y">
                  {docs.map((doc) => {
                    const isImporting = importingId === doc.id;
                    return (
                      <li key={doc.id}>
                        <button
                          type="button"
                          onClick={() => pick(doc)}
                          disabled={importingId !== null}
                          className="hover:bg-accent flex w-full items-center gap-3 px-3 py-2 text-left text-sm disabled:opacity-60"
                        >
                          {isImporting ? (
                            <Loader2 className="text-muted-foreground size-4 shrink-0 animate-spin" />
                          ) : (
                            <FileText className="text-muted-foreground size-4 shrink-0" />
                          )}
                          <div className="min-w-0 flex-1">
                            <div className="truncate font-medium">{doc.name}</div>
                            {doc.modified_time && (
                              <div className="text-muted-foreground text-xs">
                                {formatDate(doc.modified_time)}
                              </div>
                            )}
                          </div>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </ScrollArea>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
