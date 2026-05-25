import { apiFetchAuthed } from "@/lib/api-client";

import type {
  CreateProjectBody,
  MoveStageBody,
  Project,
  ProjectListResponse,
  UpdateProjectBody,
} from "./types";

export interface ListProjectsParams {
  /** Filter by stage *key* (e.g. `"idea"`). Per-department; resolves to the matching stage row. */
  stage?: string;
  owner_id?: string;
  filter?: "mine";
  cursor?: string;
  limit?: number;
}

function qs(params: Record<string, unknown>): string {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== "");
  if (entries.length === 0) return "";
  const usp = new URLSearchParams();
  for (const [k, v] of entries) usp.set(k, String(v));
  return `?${usp.toString()}`;
}

export function listProjects(params: ListProjectsParams = {}): Promise<ProjectListResponse> {
  return apiFetchAuthed<ProjectListResponse>(`/projects${qs({ ...params })}`);
}

export function getProject(id: string): Promise<Project> {
  return apiFetchAuthed<Project>(`/projects/${id}`);
}

export function createProject(body: CreateProjectBody): Promise<Project> {
  return apiFetchAuthed<Project>("/projects", {
    method: "POST",
    body: body as unknown as BodyInit,
  });
}

export function updateProject(id: string, body: UpdateProjectBody): Promise<Project> {
  return apiFetchAuthed<Project>(`/projects/${id}`, {
    method: "PATCH",
    body: body as unknown as BodyInit,
  });
}

/**
 * Move the project to another stage. Accepts either a `stage_id` (preferred)
 * or the stage `key` (legacy fallback). The backend resolves the key inside
 * the project's department.
 */
export function moveStage(id: string, target: MoveStageBody): Promise<Project> {
  return apiFetchAuthed<Project>(`/projects/${id}/stage`, {
    method: "POST",
    body: target as unknown as BodyInit,
  });
}

export function deleteProject(id: string): Promise<void> {
  return apiFetchAuthed<void>(`/projects/${id}`, { method: "DELETE" });
}

export function restoreProject(id: string): Promise<Project> {
  return apiFetchAuthed<Project>(`/projects/${id}/restore`, { method: "POST" });
}
