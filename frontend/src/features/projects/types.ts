import type { Category, PipelineStage } from "@/lib/enums";

export interface OwnerPublic {
  id: string;
  name: string;
  avatar_url: string | null;
}

export interface Project {
  id: string;
  title: string;
  description: string | null;
  category: Category;
  stage: PipelineStage;
  owner_id: string;
  owner: OwnerPublic;
  due_date: string | null;
  script_locked_at: string | null;
  script_locked_by: string | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

export interface ProjectListResponse {
  items: Project[];
  next_cursor: string | null;
}

export interface CreateProjectBody {
  title: string;
  category: Category;
  description?: string | null;
  due_date?: string | null;
}

export interface UpdateProjectBody {
  title?: string;
  description?: string | null;
  category?: Category;
  due_date?: string | null;
}
