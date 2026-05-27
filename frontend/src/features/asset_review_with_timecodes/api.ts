import { apiFetchAuthed } from "@/lib/api-client";

import type {
  EditApprovalSummary,
  EditComment,
  EditVersion,
  FinaliseEditBody,
  InitUploadBody,
  InitUploadResponse,
  PlaybackUrlResponse,
} from "./types";

export function listEdits(projectId: string): Promise<EditVersion[]> {
  return apiFetchAuthed<EditVersion[]>(`/projects/${projectId}/edits`);
}

export function initUpload(
  projectId: string,
  body: InitUploadBody,
): Promise<InitUploadResponse> {
  return apiFetchAuthed<InitUploadResponse>(`/projects/${projectId}/edits/init-upload`, {
    method: "POST",
    body: body as unknown as BodyInit,
  });
}

export function finaliseEdit(projectId: string, body: FinaliseEditBody): Promise<EditVersion> {
  return apiFetchAuthed<EditVersion>(`/projects/${projectId}/edits`, {
    method: "POST",
    body: body as unknown as BodyInit,
  });
}

export function getPlaybackUrl(editId: string): Promise<PlaybackUrlResponse> {
  return apiFetchAuthed<PlaybackUrlResponse>(`/edits/${editId}/playback-url`);
}

export function approveEdit(editId: string): Promise<EditVersion> {
  return apiFetchAuthed<EditVersion>(`/edits/${editId}/approve`, { method: "POST" });
}

export function getEditApprovals(editId: string): Promise<EditApprovalSummary> {
  return apiFetchAuthed<EditApprovalSummary>(`/edits/${editId}/approvals`);
}

export function requestChanges(editId: string, notes: string): Promise<EditVersion> {
  return apiFetchAuthed<EditVersion>(`/edits/${editId}/request-changes`, {
    method: "POST",
    body: { notes } as unknown as BodyInit,
  });
}

export function listEditComments(editId: string): Promise<EditComment[]> {
  return apiFetchAuthed<EditComment[]>(`/edits/${editId}/comments`);
}

export function addEditComment(
  editId: string,
  body: string,
  timestamp_seconds: number,
): Promise<EditComment> {
  return apiFetchAuthed<EditComment>(`/edits/${editId}/comments`, {
    method: "POST",
    body: { body, timestamp_seconds } as unknown as BodyInit,
  });
}

export function resolveEditComment(commentId: string): Promise<EditComment> {
  return apiFetchAuthed<EditComment>(`/edits/comments/${commentId}/resolve`, {
    method: "POST",
  });
}

export function reopenEditComment(commentId: string): Promise<EditComment> {
  return apiFetchAuthed<EditComment>(`/edits/comments/${commentId}/reopen`, {
    method: "POST",
  });
}

export function dispatchEditComments(
  editId: string,
): Promise<{ dispatched: number }> {
  return apiFetchAuthed<{ dispatched: number }>(
    `/edits/${editId}/dispatch-comments`,
    { method: "POST" },
  );
}
