import { apiFetchAuthed } from "@/lib/api-client";

import type { DepartmentPermissions } from "./types";

export function getMyPermissions(departmentId: string): Promise<DepartmentPermissions> {
  return apiFetchAuthed<DepartmentPermissions>(
    `/me/permissions?department_id=${encodeURIComponent(departmentId)}`,
  );
}
