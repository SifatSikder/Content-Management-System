"use client";

import { useMemo } from "react";

import { getStages, type StageSpec } from "@/features/projects/lib/stagesByTemplate";

/**
 * Synchronous stage list for a department template.
 *
 * Pre-2026-05-26 this was an async fetch from `/departments/{id}/stages`.
 * The stages table was dropped; stages now live in code keyed by
 * `template_key` (see `frontend/src/features/projects/lib/stagesByTemplate`).
 * Callers swap from passing `departmentId` to passing the parent
 * department's `template_key`.
 */
export function useTemplateStages(
  templateKey: string | null | undefined,
): StageSpec[] {
  return useMemo(() => getStages(templateKey), [templateKey]);
}
