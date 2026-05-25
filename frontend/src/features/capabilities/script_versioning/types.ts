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
