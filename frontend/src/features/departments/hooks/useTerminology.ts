"use client";

import { useLocale } from "next-intl";
import { useCallback } from "react";

import type { Terminology } from "@/features/departments/types";

/**
 * Per-noun terminology lookup for a department.
 *
 * Returns a callable `noun(key, fallback) -> string` that resolves a generic
 * label to the department's override for the current locale, falling back
 * to the supplied default i18n string when the template doesn't carry an
 * override for this noun.
 *
 * Example:
 *
 *   const noun = useTerminology(project.department.terminology);
 *   const buttonLabel = noun("create_project", t("projects.create"));
 *   // In Content Creation: "New project"
 *   // In Marketing: "New lead" (terminology.create_project.en = "New lead")
 *
 * The fallback chain inside one noun is `locale → en → nl → fallback`,
 * mirroring the stage-label resolver in `useStageLabel`.
 */
export function useTerminology(
  terminology: Terminology | null | undefined,
): (key: string, fallback: string) => string {
  const locale = useLocale();
  return useCallback(
    (key: string, fallback: string) => {
      if (!terminology) return fallback;
      const entry = terminology[key];
      if (!entry) return fallback;
      return entry[locale] ?? entry.en ?? entry.nl ?? fallback;
    },
    [terminology, locale],
  );
}
