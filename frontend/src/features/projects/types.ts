import type { Category, PipelineStage } from "@/lib/enums";

export interface OwnerPublic {
  id: string;
  name: string;
  avatar_url: string | null;
}

/**
 * Stage projection embedded in `Project.stage` — what the kanban column +
 * header badge need to render. Mirrors `app/schemas/project.py::StagePublic`.
 */
export interface ProjectStage {
  id: string;
  key: string;
  name_i18n: Record<string, string>;
  order_index: number;
  is_terminal: boolean;
  color: string | null;
}

/**
 * Minimal department embed on a project response — surfaces `capabilities`
 * so the project detail page can decide which capability tabs to render
 * without a second round-trip. Mirrors `app/schemas/project.py::DepartmentEmbed`.
 */
export interface ProjectDepartment {
  id: string;
  name: string;
  slug: string;
  capabilities: string[];
}

export interface Project {
  id: string;
  title: string;
  description: string | null;
  category: Category;
  business_id: string;
  department_id: string;
  stage_id: string;
  stage: ProjectStage;
  department: ProjectDepartment;
  owner_id: string;
  owner: OwnerPublic;
  due_date: string | null;
  script_locked_at: string | null;
  script_locked_by: string | null;
  drive_folder_id: string | null;
  drive_folder_url: string | null;
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
  department_id: string;
  description?: string | null;
  due_date?: string | null;
  owner_id?: string;
  stage_id?: string;
}

export interface UpdateProjectBody {
  title?: string;
  description?: string | null;
  category?: Category;
  due_date?: string | null;
}

/** Body for POST /projects/{id}/stage — supply either id (preferred) or key. */
export interface MoveStageBody {
  stage_id?: string;
  stage_key?: string;
}

/**
 * Legacy helper: returns the project's stage as the old PipelineStage string
 * literal where it matches. New code should prefer `project.stage.key`. Kept
 * for incremental migration of components that still narrow on the enum.
 */
export function legacyStageKey(project: Project): PipelineStage {
  return project.stage.key as PipelineStage;
}
