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

import { ParticipantRosterTab } from "@/features/capabilities/participant_roster/ParticipantRosterTab";
import { EditsTab } from "@/features/capabilities/asset_review_with_timecodes/components/EditsTab";
import { LocationTab } from "@/features/capabilities/location_scouting/components/LocationTab";
import { ScriptTab } from "@/features/capabilities/script_versioning/components/ScriptTab";
import { ShootTab } from "@/features/capabilities/event_scheduling/components/ShootTab";
import { type Role } from "@/features/auth/constants";
import type { Project } from "@/features/projects/types";

/**
 * Props every capability tab receives. Tabs ignore fields they don't need.
 * Permission decisions inside the tab go through `useCanIDo` from
 * `features/permissions`; `role` + `isOwner` stay on the props because some
 * tabs still surface owner-only labels (e.g. "Owned by you") that don't
 * map to action keys. Capability tabs that don't need them can ignore both.
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
   * Action keys this capability ships — mirror of the backend
   * `Capability.permission_actions` tuple. Surfaced in the permission matrix
   * so a CEO can toggle them without typing raw `<cap>.<verb>` strings.
   */
  permissionActions: readonly string[];
  /**
   * The tab component rendered when a department has this capability enabled.
   * Typed as `ComponentType<any>` because the existing tabs have slightly
   * different prop shapes (some require `role`/`isOwner`, others don't);
   * Phase D unifies them.
   */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  ProjectTab: ComponentType<any>;
}

// Declaration order is the tab order on the project detail page. We order
// the five Content Creation capabilities in natural production-flow sequence
// — Script → Locations → Casting → Shoots → Edits — so a CEO scanning a
// project's tabs reads them top-to-bottom as the actual pipeline stages.
// `enabledCapabilities` preserves this order via `Object.values()` (insertion
// order is stable on modern JS engines).
export const CAPABILITY_REGISTRY: Record<string, CapabilityEntry> = {
  script_versioning: {
    key: "script_versioning",
    tabLabelKey: "tab_script",
    name: "Script",
    permissionActions: ["script_versioning.lock", "script_versioning.unlock"],
    ProjectTab: ScriptTab,
  },
  location_scouting: {
    key: "location_scouting",
    tabLabelKey: "tab_location",
    name: "Locations",
    permissionActions: [],
    ProjectTab: LocationTab,
  },
  participant_roster: {
    key: "participant_roster",
    tabLabelKey: "tab_casting",
    name: "Casting",
    permissionActions: [],
    // ParticipantRosterTab dispatches between the cast and lead forms based
    // on the department's `capability_configs.participant_roster.kind`.
    ProjectTab: ParticipantRosterTab,
  },
  event_scheduling: {
    key: "event_scheduling",
    tabLabelKey: "tab_shoot",
    name: "Shoots",
    permissionActions: [],
    ProjectTab: ShootTab,
  },
  asset_review_with_timecodes: {
    key: "asset_review_with_timecodes",
    tabLabelKey: "tab_edits",
    name: "Edits",
    permissionActions: [
      "asset_review_with_timecodes.approve",
      "asset_review_with_timecodes.request_changes",
    ],
    ProjectTab: EditsTab,
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
