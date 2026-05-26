/**
 * Public DTOs for the Atlas department / stage / role / permission API.
 * Mirror `app/schemas/department.py` on the backend.
 */

/**
 * Per-noun terminology overrides. Maps a generic noun to its label per
 * locale — `{project: {en: "Lead", nl: "Lead"}}`. Empty means "use the
 * default i18n string."
 */
export type Terminology = Record<string, Record<string, string>>;

export interface Department {
  id: string;
  business_id: string;
  template_key: string | null;
  name: string;
  slug: string;
  terminology: Terminology;
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

/** Joined user info on a department membership row. */
export interface DepartmentMembershipUser {
  id: string;
  email: string;
  name: string;
  role: string;
  avatar_url: string | null;
  is_pending: boolean;
}

/** Status on the matching business_memberships row. */
export type BusinessMembershipStatus = "active" | "invited" | "revoked";

export interface DepartmentMembership {
  id: string;
  department_id: string;
  business_id: string;
  user_id: string;
  role_id: string;
  user: DepartmentMembershipUser;
  role: DepartmentRole;
  business_membership_id: string | null;
  business_membership_status: BusinessMembershipStatus | null;
  created_at: string;
  updated_at: string;
}

export interface DepartmentMembershipListResponse {
  items: DepartmentMembership[];
}

export interface InviteDepartmentMemberBody {
  email: string;
  name: string;
  role_id: string;
}

export interface MeDepartmentEntry {
  id: string;
  business_id: string;
  name: string;
  slug: string;
  role_key: string | null;
  role_name_i18n: Record<string, string> | null;
  template_key: string | null;
  terminology: Terminology;
}

export interface MeDepartmentsResponse {
  items: MeDepartmentEntry[];
}
