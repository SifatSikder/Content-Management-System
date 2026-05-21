"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { fetchPrefs, patchPrefs } from "@/features/notification-prefs/api";
import type { NotificationPrefs } from "@/features/notification-prefs/types";

const ROWS: { field: keyof NotificationPrefs; i18nKey: string }[] = [
  { field: "push_project_created", i18nKey: "event_project_created" },
  { field: "push_script_submitted", i18nKey: "event_script_submitted" },
  { field: "push_script_locked", i18nKey: "event_script_locked" },
  { field: "push_cut_uploaded", i18nKey: "event_cut_uploaded" },
  { field: "push_cut_comment", i18nKey: "event_cut_comment" },
  { field: "push_cut_approved", i18nKey: "event_cut_approved" },
  { field: "push_cut_changes_requested", i18nKey: "event_cut_changes_requested" },
  { field: "push_project_published", i18nKey: "event_project_published" },
  { field: "push_project_stuck", i18nKey: "event_project_stuck" },
];

export function NotificationPrefsCard() {
  const t = useTranslations("notification_prefs");
  const [prefs, setPrefs] = useState<NotificationPrefs | null>(null);
  const [busy, setBusy] = useState<keyof NotificationPrefs | null>(null);

  useEffect(() => {
    fetchPrefs().then(setPrefs).catch(() => {
      toast.error(t("save_failed"));
    });
  }, [t]);

  async function toggle(field: keyof NotificationPrefs, next: boolean) {
    if (!prefs) return;
    const optimistic = { ...prefs, [field]: next };
    setPrefs(optimistic);
    setBusy(field);
    try {
      const saved = await patchPrefs({ [field]: next });
      setPrefs(saved);
    } catch {
      setPrefs(prefs);
      toast.error(t("save_failed"));
    } finally {
      setBusy(null);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("title")}</CardTitle>
        <CardDescription>{t("description")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-1 text-sm">
        {prefs === null && (
          <p className="text-muted-foreground">{t("loading")}</p>
        )}
        {prefs !== null && (
          <ul className="space-y-1">
            {ROWS.map(({ field, i18nKey }) => (
              <li
                key={field}
                className="flex items-center justify-between gap-3 rounded-md px-2 py-1.5"
              >
                <span>{t(i18nKey)}</span>
                <Switch
                  checked={prefs[field]}
                  disabled={busy === field}
                  onCheckedChange={(next) => toggle(field, next)}
                />
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
