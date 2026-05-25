"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { useCurrentDepartment } from "@/features/departments/hooks/useCurrentDepartment";
import { fetchPrefs, patchPref } from "@/features/notification-prefs/api";
import type { DepartmentPrefs } from "@/features/notification-prefs/types";

/**
 * Per-event opt-in/out toggles for the user's current department.
 *
 * Phase B switched the underlying schema from a fixed 9-column row to a
 * department-scoped table. The full settings page (`/settings/notifications`)
 * called out in the plan would let the user pick between departments —
 * that's a follow-up; this card just renders the current department's
 * event list inline on `/settings`.
 */
export function NotificationPrefsCard() {
  const t = useTranslations("notification_prefs");
  const locale = useLocale();
  const department = useCurrentDepartment();
  const [prefs, setPrefs] = useState<DepartmentPrefs | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    if (department.status !== "ready" || !department.current) {
      setPrefs(null);
      return;
    }
    fetchPrefs(department.current.id)
      .then(setPrefs)
      .catch(() => toast.error(t("save_failed")));
  }, [department.status, department.current, t]);

  async function toggle(eventKey: string, next: boolean) {
    if (!prefs || !department.current) return;
    const previous = prefs;
    const optimistic: DepartmentPrefs = {
      ...prefs,
      events: prefs.events.map((e) =>
        e.event_key === eventKey ? { ...e, enabled: next } : e,
      ),
    };
    setPrefs(optimistic);
    setBusy(eventKey);
    try {
      const saved = await patchPref({
        department_id: department.current.id,
        event_key: eventKey,
        enabled: next,
      });
      setPrefs(saved);
    } catch {
      setPrefs(previous);
      toast.error(t("save_failed"));
    } finally {
      setBusy(null);
    }
  }

  function label(nameI18n: Record<string, string>, fallback: string): string {
    return nameI18n[locale] ?? nameI18n.en ?? nameI18n.nl ?? fallback;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("title")}</CardTitle>
        <CardDescription>{t("description")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-1 text-sm">
        {department.status === "loading" && (
          <p className="text-muted-foreground">{t("loading")}</p>
        )}
        {department.status === "none" && (
          <p className="text-muted-foreground">{t("no_department")}</p>
        )}
        {prefs === null && department.status === "ready" && (
          <p className="text-muted-foreground">{t("loading")}</p>
        )}
        {prefs !== null && prefs.events.length === 0 && (
          <p className="text-muted-foreground">{t("no_events")}</p>
        )}
        {prefs !== null && prefs.events.length > 0 && (
          <ul className="space-y-1">
            {prefs.events.map((event) => (
              <li
                key={event.event_key}
                className="flex items-center justify-between gap-3 rounded-md px-2 py-1.5"
              >
                <span>{label(event.name_i18n, event.event_key)}</span>
                <Switch
                  checked={event.enabled}
                  disabled={busy === event.event_key}
                  onCheckedChange={(next) => toggle(event.event_key, next)}
                />
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
