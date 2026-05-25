/**
 * Frontend capability registry.
 *
 * Mirror of `app/capabilities/registry.py`. Maps a capability key to the
 * project-detail tab component that renders for that capability + the i18n
 * key for the tab label.
 *
 * The project detail page (`/projects/[id]`) reads
 * `project.department.capabilities` (the JSONB array on the department) and
 * renders only the matching tabs. A capability key listed in the registry
 * but NOT in the department's enabled list is silently skipped.
 */

import type { ComponentType } from "react";

import { CastingTab } from "@/features/casting/components/CastingTab";
import { EditsTab } from "@/features/edits/components/EditsTab";
import { LocationTab } from "@/features/locations/components/LocationTab";
import { ScriptTab } from "@/features/scripts/components/ScriptTab";
import { ShootTab } from "@/features/shoots/components/ShootTab";
import type { Role } from "@/lib/enums";
import type { Project } from "@/features/projects/types";

/**
 * Props every capability tab receives. Tabs ignore fields they don't need.
 * Permission decisions inside the tab should defer to `useCanIDo` from
 * `features/permissions`; the legacy `role`/`isOwner` props are still
 * passed because the existing tab implementations consult the deprecated
 * `lib/enums.ts` helpers for now. Phase D moves them over.
 */
export interface ProjectTabProps {
  project: Project;
  role: Role;
  isOwner: boolean;
  onProjectUpdated: (p: Project) => void;
}

export interface CapabilityEntry {
  /** Stable key matching the backend registry (`app/capabilities/registry.py`). */
  key: string;
  /** i18n key under `project_detail.*` — falls back to the registry's `name`. */
  tabLabelKey: string;
  /** Human-readable English fallback when no translation matches. */
  name: string;
  /**
   * The tab component rendered when a department has this capability enabled.
   * Typed as `ComponentType<any>` because the existing tabs have slightly
   * different prop shapes (some require `role`/`isOwner`, others don't);
   * Phase D unifies them.
   */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  ProjectTab: ComponentType<any>;
}

export const CAPABILITY_REGISTRY: Record<string, CapabilityEntry> = {
  script_versioning: {
    key: "script_versioning",
    tabLabelKey: "tab_script",
    name: "Script",
    ProjectTab: ScriptTab,
  },
  asset_review_with_timecodes: {
    key: "asset_review_with_timecodes",
    tabLabelKey: "tab_edits",
    name: "Edits",
    ProjectTab: EditsTab,
  },
  location_scouting: {
    key: "location_scouting",
    tabLabelKey: "tab_location",
    name: "Locations",
    ProjectTab: LocationTab,
  },
  participant_roster: {
    key: "participant_roster",
    tabLabelKey: "tab_casting",
    name: "Casting",
    ProjectTab: CastingTab,
  },
  event_scheduling: {
    key: "event_scheduling",
    tabLabelKey: "tab_shoot",
    name: "Shoots",
    ProjectTab: ShootTab,
  },
};

/**
 * Iterate capability keys in the registry's declaration order, filtered to
 * those the department has enabled. Departments that list an unknown key
 * (e.g. a future capability the frontend hasn't shipped yet) get it
 * silently dropped — better than rendering a blank tab.
 */
export function enabledCapabilities(
  departmentCapabilities: readonly string[],
): CapabilityEntry[] {
  const set = new Set(departmentCapabilities);
  return Object.values(CAPABILITY_REGISTRY).filter((cap) => set.has(cap.key));
}
