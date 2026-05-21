export interface NotificationPrefs {
  push_project_created: boolean;
  push_script_submitted: boolean;
  push_script_locked: boolean;
  push_cut_uploaded: boolean;
  push_cut_comment: boolean;
  push_cut_approved: boolean;
  push_cut_changes_requested: boolean;
  push_project_published: boolean;
  push_project_stuck: boolean;
}

export type NotificationPrefsPatch = Partial<NotificationPrefs>;
