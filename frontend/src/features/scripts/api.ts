import { apiFetchAuthed } from "@/lib/api-client";

import type { ScriptComment, ScriptVersion } from "./types";

export function listVersions(projectId: string): Promise<ScriptVersion[]> {
  return apiFetchAuthed<ScriptVersion[]>(`/projects/${projectId}/scripts/versions`);
}

export function createVersion(projectId: string, body_markdown: string): Promise<ScriptVersion> {
  return apiFetchAuthed<ScriptVersion>(`/projects/${projectId}/scripts/versions`, {
    method: "POST",
    body: { body_markdown } as unknown as BodyInit,
  });
}

export function submitScript(projectId: string): Promise<{ status: string }> {
  return apiFetchAuthed(`/projects/${projectId}/scripts/submit`, { method: "POST" });
}

export function lockScript(projectId: string): Promise<{ status: string }> {
  return apiFetchAuthed(`/projects/${projectId}/scripts/lock`, { method: "POST" });
}

export function unlockScript(projectId: string): Promise<{ status: string }> {
  return apiFetchAuthed(`/projects/${projectId}/scripts/unlock`, { method: "POST" });
}

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
