"use client";

import { CastingTab } from "@/features/participant_roster/components/CastingTab";
import type { Project } from "@/features/projects/types";

import { LeadsTab } from "./LeadsTab";

interface Props {
  project: Project;
}

/**
 * Dispatcher for the participant-roster tab.
 *
 * Cast vs lead mode is derived from the department's `template_key`:
 *   * `marketing` → `LeadsTab`
 *   * anything else (Content Creation today, the only other template) →
 *     `CastingTab`
 *
 * The two share the underlying `participants` table + `/cast` route surface
 * — only the visible fields differ.
 */
export function ParticipantRosterTab({ project }: Props) {
  const kind = project.department.template_key === "marketing" ? "lead" : "cast";
  if (kind === "lead") return <LeadsTab project={project} />;
  return <CastingTab project={project} />;
}
