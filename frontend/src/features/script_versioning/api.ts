import { apiFetchAuthed } from "@/lib/api-client";

import type {
  CreateScriptSignoffBody,
  ScriptComment,
  ScriptSignoff,
  ScriptSummary,
  ScriptVersion,
} from "./types";

// ---------- summary + versions ----------

export function getScriptSummary(projectId: string): Promise<ScriptSummary> {
  return apiFetchAuthed<ScriptSummary>(`/projects/${projectId}/scripts`);
}

export function listVersions(projectId: string): Promise<ScriptVersion[]> {
  return apiFetchAuthed<ScriptVersion[]>(`/projects/${projectId}/scripts/versions`);
}

export function createVersion(projectId: string, body_markdown: string): Promise<ScriptVersion> {
  return apiFetchAuthed<ScriptVersion>(`/projects/${projectId}/scripts/versions`, {
    method: "POST",
    body: { body_markdown } as unknown as BodyInit,
  });
}

export function updateVersion(
  projectId: string,
  versionId: string,
  body_markdown: string,
): Promise<ScriptVersion> {
  return apiFetchAuthed<ScriptVersion>(
    `/projects/${projectId}/scripts/versions/${versionId}`,
    {
      method: "PATCH",
      body: { body_markdown } as unknown as BodyInit,
    },
  );
}

// ---------- lock / unlock ----------

export function lockScript(projectId: string): Promise<ScriptSummary> {
  return apiFetchAuthed<ScriptSummary>(`/projects/${projectId}/scripts/lock`, {
    method: "POST",
  });
}

export function unlockScript(projectId: string): Promise<ScriptSummary> {
  return apiFetchAuthed<ScriptSummary>(`/projects/${projectId}/scripts/unlock`, {
    method: "POST",
  });
}

// ---------- signoffs ----------

export function listScriptVersionSignoffs(
  projectId: string,
  versionId: string,
): Promise<ScriptSignoff[]> {
  return apiFetchAuthed<ScriptSignoff[]>(
    `/projects/${projectId}/scripts/versions/${versionId}/signoffs`,
  );
}

export function createScriptSignoff(
  projectId: string,
  versionId: string,
  body: CreateScriptSignoffBody,
): Promise<ScriptSignoff> {
  return apiFetchAuthed<ScriptSignoff>(
    `/projects/${projectId}/scripts/versions/${versionId}/signoffs`,
    {
      method: "POST",
      body: body as unknown as BodyInit,
    },
  );
}

// ---------- request enhancement ----------

export interface ScriptEnhancementCandidate {
  user_id: string;
  email: string;
  name: string;
  role_key: string;
  latest_decision: "looks_good" | "needs_changes" | null;
}

export function listScriptEnhancementCandidates(
  projectId: string,
): Promise<{ items: ScriptEnhancementCandidate[] }> {
  return apiFetchAuthed(
    `/projects/${projectId}/scripts/enhancement-candidates`,
  );
}

export function requestScriptEnhancement(
  projectId: string,
  reviewerUserIds: string[],
): Promise<{ status: string; newly_assigned_user_ids: string[] }> {
  return apiFetchAuthed(`/projects/${projectId}/scripts/request-enhancement`, {
    method: "POST",
    body: { reviewer_user_ids: reviewerUserIds } as unknown as BodyInit,
  });
}

// ---------- comments ----------

export function listComments(versionId: string): Promise<ScriptComment[]> {
  return apiFetchAuthed<ScriptComment[]>(`/scripts/versions/${versionId}/comments`);
}

export function addComment(
  versionId: string,
  body: string,
  paragraph_anchor?: string,
): Promise<ScriptComment> {
  return apiFetchAuthed<ScriptComment>(`/scripts/versions/${versionId}/comments`, {
    method: "POST",
    body: { body, paragraph_anchor: paragraph_anchor ?? null } as unknown as BodyInit,
  });
}

export function resolveComment(commentId: string): Promise<ScriptComment> {
  return apiFetchAuthed<ScriptComment>(`/scripts/comments/${commentId}/resolve`, {
    method: "POST",
  });
}

export function reopenComment(commentId: string): Promise<ScriptComment> {
  return apiFetchAuthed<ScriptComment>(`/scripts/comments/${commentId}/reopen`, {
    method: "POST",
  });
}
