import { apiFetchAuthed, localFetch } from "@/lib/api-client";

import type {
  CreateDepartmentBody,
  CreateRoleBody,
  Department,
  DepartmentListResponse,
  DepartmentMembership,
  DepartmentMembershipListResponse,
  DepartmentRole,
  InviteDepartmentMemberBody,
  MeDepartmentsResponse,
  Permission,
  PermissionListResponse,
  RoleListResponse,
  UpdateDepartmentBody,
  UpdateRoleBody,
  UpsertPermissionBody,
} from "./types";

// --- Departments ---------------------------------------------------------

export function listDepartments(businessId: string): Promise<DepartmentListResponse> {
  return apiFetchAuthed<DepartmentListResponse>(
    `/businesses/${businessId}/departments`,
  );
}

export function createDepartment(
  businessId: string,
  body: CreateDepartmentBody,
): Promise<Department> {
  return apiFetchAuthed<Department>(`/businesses/${businessId}/departments`, {
    method: "POST",
    body: body as unknown as BodyInit,
  });
}

export function getDepartment(id: string): Promise<Department> {
  return apiFetchAuthed<Department>(`/departments/${id}`);
}

export function updateDepartment(
  id: string,
  body: UpdateDepartmentBody,
): Promise<Department> {
  return apiFetchAuthed<Department>(`/departments/${id}`, {
    method: "PATCH",
    body: body as unknown as BodyInit,
  });
}

export function archiveDepartment(id: string): Promise<void> {
  return apiFetchAuthed<void>(`/departments/${id}`, { method: "DELETE" });
}

// --- Roles ---------------------------------------------------------------

export function listRoles(departmentId: string): Promise<RoleListResponse> {
  return apiFetchAuthed<RoleListResponse>(`/departments/${departmentId}/roles`);
}

export function createRole(
  departmentId: string,
  body: CreateRoleBody,
): Promise<DepartmentRole> {
  return apiFetchAuthed<DepartmentRole>(`/departments/${departmentId}/roles`, {
    method: "POST",
    body: body as unknown as BodyInit,
  });
}

export function updateRole(
  departmentId: string,
  roleId: string,
  body: UpdateRoleBody,
): Promise<DepartmentRole> {
  return apiFetchAuthed<DepartmentRole>(
    `/departments/${departmentId}/roles/${roleId}`,
    { method: "PATCH", body: body as unknown as BodyInit },
  );
}

export function deleteRole(departmentId: string, roleId: string): Promise<void> {
  return apiFetchAuthed<void>(`/departments/${departmentId}/roles/${roleId}`, {
    method: "DELETE",
  });
}

// --- Permissions ---------------------------------------------------------

export function listPermissions(roleId: string): Promise<PermissionListResponse> {
  return apiFetchAuthed<PermissionListResponse>(
    `/department-roles/${roleId}/permissions`,
  );
}

export function upsertPermission(
  roleId: string,
  body: UpsertPermissionBody,
): Promise<Permission> {
  return apiFetchAuthed<Permission>(`/department-roles/${roleId}/permissions`, {
    method: "PATCH",
    body: body as unknown as BodyInit,
  });
}

// --- Department members --------------------------------------------------

export function listDepartmentMembers(
  departmentId: string,
): Promise<DepartmentMembershipListResponse> {
  return apiFetchAuthed<DepartmentMembershipListResponse>(
    `/departments/${departmentId}/memberships`,
  );
}

/**
 * Invite a person to a department. Goes through the Next.js BFF route so
 * user-creation, invite-token, and the welcome email run alongside the
 * FastAPI membership write. See `app/api/departments/[id]/invite/route.ts`.
 */
export function inviteDepartmentMember(
  departmentId: string,
  body: InviteDepartmentMemberBody,
): Promise<DepartmentMembership & { invite_url_for_admin?: string }> {
  return localFetch<DepartmentMembership & { invite_url_for_admin?: string }>(
    `/api/departments/${departmentId}/invite`,
    {
      method: "POST",
      body: body as unknown as BodyInit,
    },
  );
}

export function removeDepartmentMember(
  departmentId: string,
  membershipId: string,
): Promise<void> {
  return apiFetchAuthed<void>(
    `/departments/${departmentId}/memberships/${membershipId}`,
    { method: "DELETE" },
  );
}

/**
 * Update an existing member's role within a department. The backend
 * `assign_department_member` service is upsert-shaped: posting the same
 * user_id with a new role_id updates the role on the existing row instead
 * of creating a duplicate.
 */
export function changeDepartmentMemberRole(
  departmentId: string,
  userId: string,
  roleId: string,
): Promise<DepartmentMembership> {
  return apiFetchAuthed<DepartmentMembership>(
    `/departments/${departmentId}/memberships`,
    {
      method: "POST",
      body: { user_id: userId, role_id: roleId } as unknown as BodyInit,
    },
  );
}

// --- Me ------------------------------------------------------------------

export function listMyDepartments(
  businessId: string,
): Promise<MeDepartmentsResponse> {
  const usp = new URLSearchParams({ business_id: businessId });
  return apiFetchAuthed<MeDepartmentsResponse>(`/me/departments?${usp.toString()}`);
}
