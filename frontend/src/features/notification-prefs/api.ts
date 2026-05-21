import { apiFetchAuthed } from "@/lib/api-client";

import type { NotificationPrefs, NotificationPrefsPatch } from "./types";

export function fetchPrefs(): Promise<NotificationPrefs> {
  return apiFetchAuthed<NotificationPrefs>("/me/notification-prefs");
}

export function patchPrefs(patch: NotificationPrefsPatch): Promise<NotificationPrefs> {
  return apiFetchAuthed<NotificationPrefs>("/me/notification-prefs", {
    method: "PATCH",
    body: patch as unknown as BodyInit,
  });
}
