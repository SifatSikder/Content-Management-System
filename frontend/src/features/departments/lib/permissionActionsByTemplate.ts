/**
 * Permission action keys exposed per department template.
 *
 * Mirrors the tab set in `frontend/src/features/projects/lib/projectTabs.ts`
 * — the permission matrix only renders the action keys that actually have
 * a feature behind them for this template. Universal `project.*` actions
 * are added by `availableActionKeys()` regardless of template.
 */

const CONTENT_CREATION_ACTIONS: readonly string[] = [
  "script_versioning.lock",
  "script_versioning.unlock",
  "script_versioning.signoff",
  "asset_review_with_timecodes.approve",
  "asset_review_with_timecodes.request_changes",
  "location.lock",
  "casting.lock",
  "raw_cut.submit",
  "department.edit_handoffs",
  "idea_versioning.lock",
  "idea_versioning.signoff",
];

const MARKETING_ACTIONS: readonly string[] = [
  // participant_roster has no capability-level permission actions today.
  // Add new lead-flow actions here as the Marketing feature surface grows.
];

export const PERMISSION_ACTIONS_BY_TEMPLATE: Record<string, readonly string[]> = {
  content_creation: CONTENT_CREATION_ACTIONS,
  marketing: MARKETING_ACTIONS,
};

export function permissionActionsForTemplate(
  templateKey: string | null | undefined,
): readonly string[] {
  if (!templateKey) return [];
  return PERMISSION_ACTIONS_BY_TEMPLATE[templateKey] ?? [];
}
