import { apiFetchAuthed } from "@/lib/api-client";

import type { DepartmentPrefs, SetEventPrefBody } from "./types";

export function fetchPrefs(departmentId: string): Promise<DepartmentPrefs> {
  return apiFetchAuthed<DepartmentPrefs>(
    `/me/notification-prefs?department_id=${encodeURIComponent(departmentId)}`,
  );
}

export function patchPref(body: SetEventPrefBody): Promise<DepartmentPrefs> {
  return apiFetchAuthed<DepartmentPrefs>("/me/notification-prefs", {
    method: "PATCH",
    body: body as unknown as BodyInit,
  });
}
