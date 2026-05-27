/**
 * Tab set per department template.
 *
 * Atlas no longer pretends features are dynamically pluggable per
 * department. The set of tabs a project shows is determined entirely by
 * the department's `template_key`. Adding a new department type = adding
 * an entry to this map plus the code that backs the tabs.
 *
 * Tabs are rendered in declaration order. The universal Brief tab is
 * always first and Activity is always last — they're not listed here.
 */

import type { ComponentType } from "react";

import { EditsTab } from "@/features/asset_review_with_timecodes/components/EditsTab";
import { ShootTab } from "@/features/event_scheduling/components/ShootTab";
import { IdeaTab } from "@/features/idea_versioning/components/IdeaTab";
import { LocationTab } from "@/features/location_scouting/components/LocationTab";
import { ParticipantRosterTab } from "@/features/participant_roster/ParticipantRosterTab";
import { ScriptTab } from "@/features/script_versioning/components/ScriptTab";
import { type Role } from "@/features/auth/constants";
import type { Project } from "@/features/projects/types";

/** Props every project tab receives. */
export interface ProjectTabProps {
  project: Project;
  role: Role;
  isOwner: boolean;
  /**
   * True if the current user is the project owner or an active assignee
   * on the project's current stage. Tabs use this to disable inputs and
   * render in a read-only mode. CEO + others who are only "watching"
   * see this as false.
   */
  canInput: boolean;
  onProjectUpdated: (p: Project) => void;
}

export interface TabEntry {
  /** Stable key used as the Tabs primitive's `value`. */
  key: string;
  /** i18n key under `project_detail.*` (e.g. `tab_script`). */
  tabLabelKey: string;
  /** English fallback when no translation matches. */
  name: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  ProjectTab: ComponentType<any>;
  /**
   * Tab is visible to the current user only if they hold at least one of
   * these permission action keys (CEO super-admin always sees the tab).
   * Empty / omitted = visible to anyone with project view access.
   */
  requiredAnyOf?: readonly string[];
}

const CONTENT_CREATION_TABS: TabEntry[] = [
  {
    key: "location_scouting",
    tabLabelKey: "tab_location",
    name: "Locations",
    ProjectTab: LocationTab,
    // Location is owned by the Asst CEO — only the lifecycle roles see it.
    requiredAnyOf: ["location.lock", "project.create"],
  },
  {
    key: "idea_versioning",
    tabLabelKey: "tab_idea",
    name: "Idea",
    ProjectTab: IdeaTab,
    // Asst CEO authors, CEO + Director sign off.
    requiredAnyOf: [
      "idea_versioning.lock",
      "idea_versioning.signoff",
      "project.create",
    ],
  },
  {
    key: "script_versioning",
    tabLabelKey: "tab_script",
    name: "Script",
    ProjectTab: ScriptTab,
    // Asst CEO + Director draft; CEO + Asst CEO lock.
    requiredAnyOf: [
      "script_versioning.lock",
      "script_versioning.unlock",
      "project.create",
    ],
  },
  {
    key: "participant_roster",
    tabLabelKey: "tab_casting",
    name: "Casting",
    ProjectTab: ParticipantRosterTab,
    // Casting is Asst CEO only.
    requiredAnyOf: ["casting.lock", "project.create"],
  },
  {
    key: "event_scheduling",
    tabLabelKey: "tab_shoot",
    name: "Shoots",
    ProjectTab: ShootTab,
    // Director runs shoots + Asst CEO monitors.
    requiredAnyOf: ["raw_cut.submit", "project.create"],
  },
  {
    key: "asset_review_with_timecodes",
    tabLabelKey: "tab_edits",
    name: "Edits",
    ProjectTab: EditsTab,
    // Editor uploads; CEO + Asst CEO review.
    requiredAnyOf: [
      "asset_review_with_timecodes.approve",
      "asset_review_with_timecodes.request_changes",
      "stage.move:editing->edit_review",
    ],
  },
];

const MARKETING_TABS: TabEntry[] = [
  {
    key: "participant_roster",
    tabLabelKey: "tab_leads",
    name: "Leads",
    ProjectTab: ParticipantRosterTab,
  },
];

export const TABS_BY_TEMPLATE: Record<string, TabEntry[]> = {
  content_creation: CONTENT_CREATION_TABS,
  marketing: MARKETING_TABS,
};

/**
 * Which tab should open by default when a user lands on a project in
 * this stage. Used by the project detail page as the Tabs `defaultValue`
 * — the user can still click any other (visible) tab afterwards. Stages
 * not listed here fall back to "brief".
 */
const STAGE_TO_TAB_BY_TEMPLATE: Record<string, Record<string, string>> = {
  content_creation: {
    location_scouting: "location_scouting",
    draft_idea: "idea_versioning",
    script_drafting: "script_versioning",
    script_review: "script_versioning",
    casting: "participant_roster",
    shoot_schedule: "event_scheduling",
    shoot_in_progress: "event_scheduling",
    shoot_done: "asset_review_with_timecodes",
    editing: "asset_review_with_timecodes",
    edit_review: "asset_review_with_timecodes",
    approved_published: "asset_review_with_timecodes",
  },
  marketing: {},
};

export function defaultTabForStage(
  templateKey: string | null | undefined,
  stageKey: string | null | undefined,
): string | null {
  if (!templateKey || !stageKey) return null;
  return STAGE_TO_TAB_BY_TEMPLATE[templateKey]?.[stageKey] ?? null;
}

/**
 * Resolve a department's tab list. Returns `[]` for unknown / missing
 * templates — the Brief + Activity tabs still render on the page, but no
 * middle tabs do.
 */
export function tabsForTemplate(templateKey: string | null | undefined): TabEntry[] {
  if (!templateKey) return [];
  return TABS_BY_TEMPLATE[templateKey] ?? [];
}
