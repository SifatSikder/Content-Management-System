/**
 * String-literal mirrors of the legacy Postgres enums in
 * `app/models/enums.py` (Phase 1).
 *
 * **DEPRECATED for permission decisions.** Per-department roles + stages
 * live in the DB now (Phase B). Use `features/permissions/hooks/usePermissions`
 * + the upcoming `useDepartmentStages(departmentId)` hook for permission
 * checks and stage lists.
 *
 * The type aliases (`Role`, `PipelineStage`, `Category`, `EditStatus`) stay
 * because the legacy `projects.stage` enum column is still on disk during
 * the Phase B transition; the predicate helpers below (`canMoveToStage`,
 * `canEditProject`) are kept ONLY as a fallback for projects that haven't
 * been backfilled into a department yet. New call sites should not use them.
 */

export const ROLES = [
  "ceo",
  "assistant_director",
  "junior_director",
  "editor",
  "crew",
  "viewer",
] as const;
export type Role = (typeof ROLES)[number];

export const CATEGORIES = [
  "property_tour",
  "agent_intro",
  "neighbourhood",
  "testimonial",
  "other",
] as const;
export type Category = (typeof CATEGORIES)[number];

export const PIPELINE_STAGES = [
  "idea",
  "script_drafting",
  "script_review",
  "script_locked",
  "location_scouting",
  "casting",
  "shoot_scheduled",
  "shoot_done",
  "editing",
  "final_review",
  "approved_published",
] as const;
export type PipelineStage = (typeof PIPELINE_STAGES)[number];

export const EDIT_STATUSES = ["in_review", "changes_requested", "approved"] as const;
export type EditStatus = (typeof EDIT_STATUSES)[number];

/** Roles allowed to create projects. */
export const CREATOR_ROLES: ReadonlySet<Role> = new Set([
  "ceo",
  "assistant_director",
  "junior_director",
]);

/** Roles allowed to lock a script. */
export const SCRIPT_LOCKER_ROLES: ReadonlySet<Role> = new Set([
  "ceo",
  "assistant_director",
  "junior_director",
]);

/** Roles allowed to unlock a script. */
export const SCRIPT_UNLOCKER_ROLES: ReadonlySet<Role> = new Set([
  "ceo",
  "assistant_director",
]);

/** Roles allowed to approve a cut. */
export const APPROVER_ROLES: ReadonlySet<Role> = new Set(["ceo", "assistant_director"]);

/** Roles allowed to request changes on a cut. */
export const CHANGE_REQUESTER_ROLES: ReadonlySet<Role> = new Set([
  "ceo",
  "assistant_director",
  "junior_director",
]);

export function canMoveToStage(role: Role, stage: PipelineStage, isOwner: boolean): boolean {
  if (stage === "approved_published") return role === "ceo";
  if (role === "ceo" || role === "assistant_director") return true;
  if (role === "junior_director") return isOwner;
  return false;
}

export function canEditProject(role: Role, isOwner: boolean): boolean {
  if (role === "ceo" || role === "assistant_director") return true;
  if (role === "junior_director" || role === "editor") return isOwner;
  return false;
}
