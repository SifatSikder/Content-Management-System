/**
 * Permission action-key → human display mapping.
 *
 * Action keys are the wire format (`project.edit`, `script_versioning.lock`,
 * `stage.move:idea->script_drafting`); they're great for the backend gate
 * but a poor scan for a CEO toggling permissions. This helper resolves a
 * key into `{ title, description, group }` so the matrix editor can render
 * grouped, readable rows.
 *
 * Static keys (project + capability actions) are hardcoded here — there
 * are ~10 of them and they change at the same cadence as the backend
 * capability registry. Dynamic `stage.move:<from>-><to>` keys resolve via
 * the per-department stage label lookup so renaming a stage immediately
 * flows through the picker too.
 */

import { CAPABILITY_REGISTRY } from "@/features/capabilities/registry";
import type { Stage } from "@/features/departments/types";

export type PermissionGroup =
  | "project"
  | "stage"
  | "script_versioning"
  | "asset_review_with_timecodes"
  | "location_scouting"
  | "participant_roster"
  | "event_scheduling"
  | "other";

export interface PermissionDisplay {
  title: string;
  description: string;
  group: PermissionGroup;
  /** Section header rendered above the row. */
  groupLabel: string;
}

type StaticEntry = Omit<PermissionDisplay, "groupLabel">;

const STATIC_LABELS: Record<string, StaticEntry> = {
  "project.create": {
    title: "Create projects",
    description: "Start new projects in this department.",
    group: "project",
  },
  "project.view": {
    title: "View projects",
    description: "Read projects and their sub-resources.",
    group: "project",
  },
  "project.edit": {
    title: "Edit projects",
    description: "Modify project fields and nested resources.",
    group: "project",
  },
  "project.delete": {
    title: "Delete projects",
    description: "Soft-delete projects. Restorable for 30 days.",
    group: "project",
  },
  "script_versioning.lock": {
    title: "Lock script",
    description: "Freeze the current script so further edits are blocked.",
    group: "script_versioning",
  },
  "script_versioning.unlock": {
    title: "Unlock script",
    description: "Allow further edits to a previously locked script.",
    group: "script_versioning",
  },
  "asset_review_with_timecodes.approve": {
    title: "Approve cut",
    description: "Sign off on an uploaded edit.",
    group: "asset_review_with_timecodes",
  },
  "asset_review_with_timecodes.request_changes": {
    title: "Request changes",
    description: "Send the cut back to editing with comments.",
    group: "asset_review_with_timecodes",
  },
};

const GROUP_LABELS: Record<PermissionGroup, string> = {
  project: "Projects",
  stage: "Stage transitions",
  script_versioning: CAPABILITY_REGISTRY.script_versioning?.name ?? "Script versioning",
  asset_review_with_timecodes:
    CAPABILITY_REGISTRY.asset_review_with_timecodes?.name ?? "Asset review",
  location_scouting: CAPABILITY_REGISTRY.location_scouting?.name ?? "Location scouting",
  participant_roster: CAPABILITY_REGISTRY.participant_roster?.name ?? "Participant roster",
  event_scheduling: CAPABILITY_REGISTRY.event_scheduling?.name ?? "Event scheduling",
  other: "Other",
};

/** Render-order priority. Anything not listed falls into `other`. */
export const PERMISSION_GROUP_ORDER: readonly PermissionGroup[] = [
  "project",
  "stage",
  "script_versioning",
  "location_scouting",
  "participant_roster",
  "asset_review_with_timecodes",
  "event_scheduling",
  "other",
];

function titleCase(s: string): string {
  return s
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * Resolve an action key into its display shape.
 *
 * `resolveStage` is the lookup from `useStageLabel(departmentId)` — pass it
 * in so the matrix doesn't need to refetch stages itself.
 */
export function permissionDisplay(
  actionKey: string,
  resolveStage: (stageKey: string) => string,
): PermissionDisplay {
  // stage.move:<from>-><to>
  const stageMatch = actionKey.match(/^stage\.move:([^-]+(?:-[^>]+)*)->(.+)$/);
  if (stageMatch) {
    const from = resolveStage(stageMatch[1]);
    const to = resolveStage(stageMatch[2]);
    return {
      title: `${from} → ${to}`,
      description: `Move projects from ${from} to ${to}.`,
      group: "stage",
      groupLabel: GROUP_LABELS.stage,
    };
  }

  const known = STATIC_LABELS[actionKey];
  if (known) {
    return { ...known, groupLabel: GROUP_LABELS[known.group] };
  }

  // Fallback: try to associate the key with a known capability by prefix.
  const dotIndex = actionKey.indexOf(".");
  if (dotIndex !== -1) {
    const prefix = actionKey.slice(0, dotIndex);
    const cap = CAPABILITY_REGISTRY[prefix];
    if (cap) {
      const group = (prefix as PermissionGroup) in GROUP_LABELS
        ? (prefix as PermissionGroup)
        : "other";
      return {
        title: titleCase(actionKey.slice(dotIndex + 1)),
        description: `${cap.name} action.`,
        group,
        groupLabel: GROUP_LABELS[group] ?? cap.name,
      };
    }
  }

  return {
    title: actionKey,
    description: "Custom action.",
    group: "other",
    groupLabel: GROUP_LABELS.other,
  };
}

/** Static actions every department exposes regardless of capabilities. */
const PROJECT_ACTIONS: readonly string[] = [
  "project.create",
  "project.view",
  "project.edit",
  "project.delete",
];

/**
 * Enumerate every action key the matrix should render rows for in this
 * department:
 *   * project.* — always
 *   * capability action keys — only for capabilities enabled on the dept
 *   * stage.move:<from>-><to> — derived from each stage's
 *     `allowed_from_stage_ids` (so the picker matches the runtime workflow)
 *
 * Rows already in the DB whose key isn't in this list (e.g. a backend
 * action the frontend registry hasn't shipped yet) still render — the
 * matrix merges this list with the persisted rows.
 */
export function availableActionKeys(
  capabilities: readonly string[],
  stages: readonly Stage[],
): string[] {
  const keys: string[] = [...PROJECT_ACTIONS];

  for (const cap of capabilities) {
    const entry = CAPABILITY_REGISTRY[cap];
    if (entry) keys.push(...entry.permissionActions);
  }

  // Stage transitions: target.allowed_from_stage_ids tells us which source
  // stages can flow into `target`. Resolve those ids back to stage keys.
  const byId = new Map(stages.map((s) => [s.id, s] as const));
  for (const target of stages) {
    for (const fromId of target.allowed_from_stage_ids) {
      const from = byId.get(fromId);
      if (!from) continue;
      keys.push(`stage.move:${from.key}->${target.key}`);
    }
  }

  return keys;
}

