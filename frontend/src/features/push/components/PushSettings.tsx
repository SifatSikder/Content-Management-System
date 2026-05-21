"use client";

import { Bell, BellOff } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  disablePush,
  enablePush,
  getCurrentSubscription,
  pushSupported,
} from "@/features/push/lib/push";

type Status = "loading" | "unsupported" | "denied" | "subscribed" | "unsubscribed";

export function PushSettings() {
  const t = useTranslations("push");
  const [status, setStatus] = useState<Status>("loading");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    if (!pushSupported()) {
      setStatus("unsupported");
      return;
    }
    if (typeof Notification !== "undefined" && Notification.permission === "denied") {
      setStatus("denied");
      return;
    }
    const sub = await getCurrentSubscription();
    setStatus(sub ? "subscribed" : "unsubscribed");
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function onEnable() {
    setBusy(true);
    try {
      await enablePush();
      toast.success(t("enabled_toast"));
      await refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("enable_failed"));
    } finally {
      setBusy(false);
    }
  }

  async function onDisable() {
    setBusy(true);
    try {
      await disablePush();
      toast.success(t("disabled_toast"));
      await refresh();
    } catch {
      toast.error(t("disable_failed"));
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
          <p className="text-muted-foreground">{t("checking")}</p>
        )}
        {status === "unsupported" && (
          <p className="text-muted-foreground">{t("unsupported")}</p>
        )}
        {status === "denied" && (
          <p className="text-muted-foreground">{t("denied")}</p>
        )}
        {status === "subscribed" && (
          <div className="flex items-center justify-between gap-3">
            <p className="flex items-center gap-2">
              <Bell className="size-4" />
              {t("subscribed")}
            </p>
            <Button variant="outline" size="sm" onClick={onDisable} disabled={busy}>
              <BellOff className="mr-1.5 size-4" />
              {t("disable")}
            </Button>
          </div>
        )}
        {status === "unsubscribed" && (
          <div className="flex items-center justify-between gap-3">
            <p className="text-muted-foreground flex items-center gap-2">
              <BellOff className="size-4" />
              {t("unsubscribed")}
            </p>
            <Button size="sm" onClick={onEnable} disabled={busy}>
              <Bell className="mr-1.5 size-4" />
              {t("enable")}
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
