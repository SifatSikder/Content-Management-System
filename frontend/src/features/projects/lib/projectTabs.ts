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
}

const CONTENT_CREATION_TABS: TabEntry[] = [
  {
    key: "location_scouting",
    tabLabelKey: "tab_location",
    name: "Locations",
    ProjectTab: LocationTab,
  },
  {
    key: "idea_versioning",
    tabLabelKey: "tab_idea",
    name: "Idea",
    ProjectTab: IdeaTab,
  },
  {
    key: "script_versioning",
    tabLabelKey: "tab_script",
    name: "Script",
    ProjectTab: ScriptTab,
  },
  {
    key: "participant_roster",
    tabLabelKey: "tab_casting",
    name: "Casting",
    ProjectTab: ParticipantRosterTab,
  },
  {
    key: "event_scheduling",
    tabLabelKey: "tab_shoot",
    name: "Shoots",
    ProjectTab: ShootTab,
  },
  {
    key: "asset_review_with_timecodes",
    tabLabelKey: "tab_edits",
    name: "Edits",
    ProjectTab: EditsTab,
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
 * Resolve a department's tab list. Returns `[]` for unknown / missing
 * templates — the Brief + Activity tabs still render on the page, but no
 * middle tabs do.
 */
export function tabsForTemplate(templateKey: string | null | undefined): TabEntry[] {
  if (!templateKey) return [];
  return TABS_BY_TEMPLATE[templateKey] ?? [];
}
