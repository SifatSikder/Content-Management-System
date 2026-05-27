import { type Category } from "@/features/projects/constants";

export interface OwnerPublic {
  id: string;
  name: string;
  avatar_url: string | null;
}

/**
 * Minimal department embed on a project response — surfaces `template_key`
 * (drives the per-template tab map + stage registry lookup) + `terminology`
 * (per-noun i18n overrides). Mirrors `app/schemas/project.py::DepartmentEmbed`.
 */
export interface ProjectDepartment {
  id: string;
  name: string;
  slug: string;
  template_key: string | null;
  terminology: Record<string, Record<string, string>>;
}

export interface Project {
  id: string;
  title: string;
  description: string | null;
  category: Category;
  business_id: string;
  department_id: string;
  /** Stage key from the department template's `STAGES` registry. */
  stage_key: string;
  department: ProjectDepartment;
  owner_id: string;
  owner: OwnerPublic;
  due_date: string | null;
  script_locked_at: string | null;
  script_locked_by: string | null;
  location_locked_at: string | null;
  location_locked_by: string | null;
  casting_locked_at: string | null;
  casting_locked_by: string | null;
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
  stage_key?: string;
}

export interface UpdateProjectBody {
  title?: string;
  description?: string | null;
  category?: Category;
  due_date?: string | null;
}

/** Body for POST /projects/{id}/stage. */
export interface MoveStageBody {
  stage_key: string;
}

export interface AssignmentPublic {
  id: string;
  project_id: string;
  stage_key: string;
  user_id: string;
  user: OwnerPublic;
  assigned_at: string;
  assigned_by: string | null;
}

export interface AssignmentListResponse {
  items: AssignmentPublic[];
}

