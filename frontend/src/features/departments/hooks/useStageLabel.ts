"use client";

import { useLocale } from "next-intl";
import { useMemo } from "react";

import { useDepartmentStages } from "@/features/departments/hooks/useDepartmentStages";

/**
 * Resolve a stage `key` (e.g. `"idea"`) to its localized display name
 * within a given department.
 *
 * Returns a lookup function so callers can render many stage labels from
 * one hook invocation. Until the stages load the lookup returns the raw
 * key — better than a flash-of-empty for a kanban-style component.
 */
export function useStageLabel(
  departmentId: string | null | undefined,
): (key: string) => string {
  const locale = useLocale();
  const { stages } = useDepartmentStages(departmentId);
  return useMemo(() => {
    const byKey = new Map(stages.map((s) => [s.key, s] as const));
    return (key: string) => {
      const stage = byKey.get(key);
      if (!stage) return key;
      return stage.name_i18n[locale] ?? stage.name_i18n.en ?? stage.name_i18n.nl ?? key;
    };
  }, [stages, locale]);
}
