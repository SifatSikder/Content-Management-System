"use client";

import { FolderOpen, Loader2, LogOut } from "lucide-react";
import { useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  disconnectDrive,
  getDriveConnection,
  startDriveConnect,
} from "@/features/drive/api";
import type { DriveConnection } from "@/features/drive/types";
import { ApiError } from "@/lib/api-client";

type Status = "loading" | "disconnected" | "connected";

export function DriveSettings() {
  const t = useTranslations("drive");
  const params = useSearchParams();
  const [status, setStatus] = useState<Status>("loading");
  const [connection, setConnection] = useState<DriveConnection | null>(null);
  const [busy, setBusy] = useState(false);
  const flashedRef = useRef(false);

  const refresh = useCallback(async () => {
    try {
      const conn = await getDriveConnection();
      setConnection(conn);
      setStatus(conn ? "connected" : "disconnected");
    } catch (err) {
      if (err instanceof ApiError && err.status === 503) {
        // Server is missing GOOGLE_DRIVE_* env — surface a no-op state, no toast.
        setStatus("disconnected");
        return;
      }
      toast.error(t("load_failed"));
    }
  }, [t]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Toast once on `?drive=connected` / `?drive=error` query strings; clean URL.
  useEffect(() => {
    if (flashedRef.current) return;
    const drive = params.get("drive");
    if (!drive) return;
    flashedRef.current = true;
    if (drive === "connected") {
      toast.success(t("connected_toast"));
    } else if (drive === "error") {
      const reason = params.get("reason");
      toast.error(reason ? t("connect_failed_reason", { reason }) : t("connect_failed"));
    }
    // Strip the query so a refresh doesn't re-toast.
    const url = new URL(window.location.href);
    url.searchParams.delete("drive");
    url.searchParams.delete("reason");
    window.history.replaceState({}, "", url.toString());
  }, [params, t]);

  async function onConnect() {
    setBusy(true);
    try {
      const { url } = await startDriveConnect();
      window.location.href = url;
    } catch (err) {
      if (err instanceof ApiError && err.status === 503) {
        toast.error(t("not_configured"));
      } else {
        toast.error(t("connect_failed"));
      }
      setBusy(false);
    }
  }

  async function onDisconnect() {
    setBusy(true);
    try {
      await disconnectDrive();
      setConnection(null);
      setStatus("disconnected");
      toast.success(t("disconnected_toast"));
    } catch {
      toast.error(t("disconnect_failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("title")}</CardTitle>
        <CardDescription>{t("description")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {status === "loading" && (
          <p className="text-muted-foreground flex items-center gap-2">
            <Loader2 className="size-4 animate-spin" />
            {t("checking")}
          </p>
        )}
        {status === "disconnected" && (
          <div className="flex items-center justify-between gap-3">
            <p className="text-muted-foreground flex items-center gap-2">
              <FolderOpen className="size-4" />
              {t("disconnected")}
            </p>
            <Button size="sm" onClick={onConnect} disabled={busy}>
              {busy ? <Loader2 className="mr-1.5 size-4 animate-spin" /> : null}
              {t("connect")}
            </Button>
          </div>
        )}
        {status === "connected" && connection && (
          <div className="flex items-center justify-between gap-3">
            <p className="flex items-center gap-2">
              <FolderOpen className="size-4" />
              {t("connected_as", { email: connection.google_email })}
            </p>
            <Button variant="outline" size="sm" onClick={onDisconnect} disabled={busy}>
              <LogOut className="mr-1.5 size-4" />
              {t("disconnect")}
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
