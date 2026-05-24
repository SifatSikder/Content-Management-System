import { apiFetchAuthed } from "@/lib/api-client";

import type {
  CreateDepartmentBody,
  CreateRoleBody,
  CreateStageBody,
  Department,
  DepartmentListResponse,
  DepartmentRole,
  MeDepartmentsResponse,
  Permission,
  PermissionListResponse,
  RoleListResponse,
  Stage,
  StageListResponse,
  UpdateDepartmentBody,
  UpdateRoleBody,
  UpdateStageBody,
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

// --- Stages --------------------------------------------------------------

export function listStages(departmentId: string): Promise<StageListResponse> {
  return apiFetchAuthed<StageListResponse>(`/departments/${departmentId}/stages`);
}

export function createStage(
  departmentId: string,
  body: CreateStageBody,
): Promise<Stage> {
  return apiFetchAuthed<Stage>(`/departments/${departmentId}/stages`, {
    method: "POST",
    body: body as unknown as BodyInit,
  });
}

export function updateStage(
  departmentId: string,
  stageId: string,
  body: UpdateStageBody,
): Promise<Stage> {
  return apiFetchAuthed<Stage>(`/departments/${departmentId}/stages/${stageId}`, {
    method: "PATCH",
    body: body as unknown as BodyInit,
  });
}

export function deleteStage(departmentId: string, stageId: string): Promise<void> {
  return apiFetchAuthed<void>(`/departments/${departmentId}/stages/${stageId}`, {
    method: "DELETE",
  });
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

// --- Me ------------------------------------------------------------------

export function listMyDepartments(
  businessId: string,
): Promise<MeDepartmentsResponse> {
  const usp = new URLSearchParams({ business_id: businessId });
  return apiFetchAuthed<MeDepartmentsResponse>(`/me/departments?${usp.toString()}`);
}
