export type SignoffDecision = "looks_good" | "needs_changes";

export interface IdeaVersion {
  id: string;
  idea_id: string;
  version_number: number;
  body_markdown: string;
  author_id: string;
  submitted_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface IdeaSignoff {
  id: string;
  idea_version_id: string;
  reviewer_id: string;
  // Populated by GET /signoffs (per-version) so the UI doesn't have to
  // join via dept memberships. Other endpoints may omit them.
  reviewer_name?: string | null;
  reviewer_avatar_url?: string | null;
  decision: SignoffDecision;
  comment: string | null;
  created_at: string;
}

export interface IdeaSummary {
  locked_at: string | null;
  locked_by: string | null;
  latest_version: IdeaVersion | null;
  latest_version_signoffs: IdeaSignoff[];
  pending_reviewer_ids: string[];
  can_lock: boolean;
  reviewer_count: number;
}

export interface CreateIdeaVersionBody {
  body_markdown: string;
}

export interface CreateIdeaSignoffBody {
  decision: SignoffDecision;
  comment?: string | null;
}
