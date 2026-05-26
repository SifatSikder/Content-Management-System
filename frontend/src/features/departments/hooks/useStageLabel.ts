"use client";

import { useLocale } from "next-intl";
import { useMemo } from "react";

import { useTemplateStages } from "@/features/departments/hooks/useTemplateStages";

/**
 * Resolve a stage `key` (e.g. `"draft_idea"`) to its localized display name
 * within a department template.
 *
 * Returns a lookup function so callers can render many stage labels from
 * one hook invocation. Pass `null` while the parent template_key is still
 * loading — the lookup will then return the raw key as a fallback.
 */
export function useStageLabel(
  templateKey: string | null | undefined,
): (key: string) => string {
  const locale = useLocale();
  const stages = useTemplateStages(templateKey);
  return useMemo(() => {
    const byKey = new Map(stages.map((s) => [s.key, s] as const));
    return (key: string) => {
      const stage = byKey.get(key);
      if (!stage) return key;
      return stage.name_i18n[locale] ?? stage.name_i18n.en ?? stage.name_i18n.nl ?? key;
    };
  }, [stages, locale]);
}
