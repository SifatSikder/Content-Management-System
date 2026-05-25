/**
 * Resolved permission map for the current user in one department. Returned
 * by `GET /me/permissions?department_id=…` and consumed by `useCanIDo`.
 *
 * `is_super_admin = true` means "every action allowed" without enumerating
 * — the CEO short-circuit. `allowed` only carries true entries; an action
 * absent from the map is implicitly denied.
 */
export type DepartmentPermissions = {
  department_id: string;
  is_super_admin: boolean;
  allowed: Record<string, boolean>;
};
