/**
 * Public DTOs for the Atlas department / stage / role / permission API.
 * Mirror `app/schemas/department.py` on the backend.
 */

export interface Department {
  id: string;
  business_id: string;
  template_key: string | null;
  name: string;
  slug: string;
  capabilities: string[];
  archived_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface DepartmentListResponse {
  items: Department[];
}

export interface CreateDepartmentBody {
  name: string;
  slug?: string;
  template_key?: string;
}

export interface UpdateDepartmentBody {
  name?: string;
  capabilities?: string[];
}

export interface Stage {
  id: string;
  department_id: string;
  business_id: string;
  key: string;
  name_i18n: Record<string, string>;
  order_index: number;
  is_terminal: boolean;
  color: string | null;
  allowed_from_stage_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface StageListResponse {
  items: Stage[];
}

export interface CreateStageBody {
  key: string;
  name_i18n: Record<string, string>;
  order_index?: number;
  is_terminal?: boolean;
  color?: string | null;
  allowed_from_stage_ids?: string[];
}

export interface UpdateStageBody {
  name_i18n?: Record<string, string>;
  order_index?: number;
  is_terminal?: boolean;
  color?: string | null;
  allowed_from_stage_ids?: string[];
}

export interface DepartmentRole {
  id: string;
  department_id: string;
  business_id: string;
  key: string;
  name_i18n: Record<string, string>;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface RoleListResponse {
  items: DepartmentRole[];
}

export interface CreateRoleBody {
  key: string;
  name_i18n: Record<string, string>;
  description?: string;
}

export interface UpdateRoleBody {
  name_i18n?: Record<string, string>;
  description?: string;
}

export interface Permission {
  id: string;
  department_role_id: string;
  action_key: string;
  allowed: boolean;
}

export interface PermissionListResponse {
  items: Permission[];
}

export interface UpsertPermissionBody {
  action_key: string;
  allowed: boolean;
}

export interface MeDepartmentEntry {
  id: string;
  business_id: string;
  name: string;
  slug: string;
  role_key: string | null;
  role_name_i18n: Record<string, string> | null;
}

export interface MeDepartmentsResponse {
  items: MeDepartmentEntry[];
}
