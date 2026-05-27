"use client";

import { CastingTab } from "@/features/participant_roster/components/CastingTab";
import type { ProjectTabProps } from "@/features/projects/lib/projectTabs";

import { LeadsTab } from "./LeadsTab";

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
 *
 * Accepts the full `ProjectTabProps` so `isOwner` + `canInput` reach the
 * downstream tab (otherwise Casting's owner-only gating reads false even
 * for the project owner).
 */
export function ParticipantRosterTab(props: ProjectTabProps) {
  const kind =
    props.project.department.template_key === "marketing" ? "lead" : "cast";
  if (kind === "lead") return <LeadsTab project={props.project} />;
  return <CastingTab {...props} />;
}
