"use client";

import { CastingTab } from "@/features/capabilities/participant_roster/components/CastingTab";
import type { Project } from "@/features/projects/types";

import { LeadsTab } from "./LeadsTab";

interface Props {
  project: Project;
}

/**
 * Dispatcher for the `participant_roster` capability.
 *
 * Reads `project.department.capability_configs.participant_roster.kind` and
 * renders the matching component:
 *
 *   * `kind === "lead"` → `LeadsTab` (Marketing's lead-list form)
 *   * anything else      → `CastingTab` (the legacy cast form)
 *
 * The two share the underlying `participants` table + `/cast` route surface
 * — only the visible fields differ. See `app/seeds/templates/marketing.py`
 * and `app/seeds/templates/content_creation.py` for the per-template config.
 */
export function ParticipantRosterTab({ project }: Props) {
  const config = project.department.capability_configs?.participant_roster as
    | { kind?: string }
    | undefined;
  const kind = config?.kind ?? "cast";
  if (kind === "lead") return <LeadsTab project={project} />;
  return <CastingTab project={project} />;
}
