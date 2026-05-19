export type ActivityAction =
  | "project.created"
  | "project.updated"
  | "project.stage_changed"
  | "project.deleted"
  | "project.restored"
  | "script.version_created"
  | "script.submitted"
  | "script.locked"
  | "script.unlocked"
  | "script.comment_added"
  | "script.comment_resolved"
  | "script.comment_reopened"
  | "edit.uploaded"
  | "edit.approved"
  | "edit.changes_requested"
  | "edit.comment_added"
  | "edit.comment_resolved"
  | "edit.comment_reopened";

export interface ActivityItem {
  id: string;
  project_id: string | null;
  actor_id: string | null;
  action: ActivityAction | string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ActivityListResponse {
  items: ActivityItem[];
  next_cursor: string | null;
}

/** Map an action verb to its message key in `activity.*`. */
export function actionMessageKey(action: string): string {
  return `verb_${action.replace(/\./g, "_")}`;
}
