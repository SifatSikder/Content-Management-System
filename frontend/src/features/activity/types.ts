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
  | "edit.comment_reopened"
  | "location.created"
  | "location.updated"
  | "location.confirmed"
  | "location.unconfirmed"
  | "location.deleted"
  | "location.photo_added"
  | "location.photo_deleted"
  | "cast.created"
  | "cast.updated"
  | "cast.confirmed"
  | "cast.unconfirmed"
  | "cast.release_uploaded"
  | "cast.deleted"
  | "shoot.created"
  | "shoot.updated"
  | "shoot.call_sheet_uploaded"
  | "shoot.transitioned"
  | "shoot.deleted";

export interface ActivityItem {
  id: string;
  project_id: string | null;
  actor_id: string | null;
  /** NULL when the actor was deleted (spec §10 PII redaction). */
  actor: { id: string; name: string } | null;
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
