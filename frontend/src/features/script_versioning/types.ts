export type ScriptSignoffDecision = "looks_good" | "needs_changes";

export interface ScriptVersion {
  id: string;
  script_id: string;
  version_number: number;
  body_markdown: string;
  author_id: string;
  submitted_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ScriptComment {
  id: string;
  version_id: string;
  author_id: string;
  body: string;
  paragraph_anchor: string | null;
  resolved_at: string | null;
  resolved_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface ScriptSignoff {
  id: string;
  script_version_id: string;
  reviewer_id: string;
  // Populated by GET /signoffs (per-version) so the UI doesn't have to
  // join via dept memberships. Other endpoints may omit them.
  reviewer_name?: string | null;
  reviewer_avatar_url?: string | null;
  decision: ScriptSignoffDecision;
  comment: string | null;
  created_at: string;
}

export interface ScriptSummary {
  locked_at: string | null;
  locked_by: string | null;
  latest_version: ScriptVersion | null;
  latest_version_signoffs: ScriptSignoff[];
  pending_reviewer_ids: string[];
  can_lock: boolean;
  reviewer_count: number;
}

export interface CreateScriptVersionBody {
  body_markdown: string;
}

export interface CreateScriptSignoffBody {
  decision: ScriptSignoffDecision;
  comment?: string | null;
}
