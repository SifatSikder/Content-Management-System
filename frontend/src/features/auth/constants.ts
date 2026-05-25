/**
 * Global user-role enum mirror.
 *
 * This is the legacy single-tenant `Role` from Phase 1, still the source
 * of truth for the CEO super-admin bit (`users.role == "ceo"`) and the
 * Team invite flow's role picker. Per-department roles live in the DB
 * (`department_roles`) and are NOT mirrored here.
 *
 * After Phase E, this is the only place `Role` is exported from on the
 * frontend.
 */

export const ROLES = [
  "ceo",
  "assistant_director",
  "junior_director",
  "editor",
  "crew",
  "viewer",
] as const;
export type Role = (typeof ROLES)[number];
