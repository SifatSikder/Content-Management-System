import { apiFetchAuthed } from "@/lib/api-client";

import type {
  CreateIdeaSignoffBody,
  CreateIdeaVersionBody,
  IdeaSignoff,
  IdeaSummary,
  IdeaVersion,
} from "./types";

export function getIdeaSummary(projectId: string): Promise<IdeaSummary> {
  return apiFetchAuthed<IdeaSummary>(`/projects/${projectId}/idea`);
}

export function listIdeaVersions(projectId: string): Promise<IdeaVersion[]> {
  return apiFetchAuthed<IdeaVersion[]>(`/projects/${projectId}/idea/versions`);
}

export function createIdeaVersion(
  projectId: string,
  body: CreateIdeaVersionBody,
): Promise<IdeaVersion> {
  return apiFetchAuthed<IdeaVersion>(`/projects/${projectId}/idea/versions`, {
    method: "POST",
    body: body as unknown as BodyInit,
  });
}

export function updateIdeaVersion(
  projectId: string,
  versionId: string,
  bodyMarkdown: string,
): Promise<IdeaVersion> {
  return apiFetchAuthed<IdeaVersion>(
    `/projects/${projectId}/idea/versions/${versionId}`,
    {
      method: "PATCH",
      body: { body_markdown: bodyMarkdown } as unknown as BodyInit,
    },
  );
}

export function createIdeaSignoff(
  projectId: string,
  versionId: string,
  body: CreateIdeaSignoffBody,
): Promise<IdeaSignoff> {
  return apiFetchAuthed<IdeaSignoff>(
    `/projects/${projectId}/idea/versions/${versionId}/signoffs`,
    {
      method: "POST",
      body: body as unknown as BodyInit,
    },
  );
}

export function lockIdea(projectId: string): Promise<IdeaSummary> {
  return apiFetchAuthed<IdeaSummary>(`/projects/${projectId}/idea/lock`, {
    method: "POST",
  });
}

export function unlockIdea(projectId: string): Promise<IdeaSummary> {
  return apiFetchAuthed<IdeaSummary>(`/projects/${projectId}/idea/unlock`, {
    method: "POST",
  });
}

export interface EnhancementCandidate {
  user_id: string;
  email: string;
  name: string;
  role_key: string;
}

export function listEnhancementCandidates(
  projectId: string,
): Promise<{ items: EnhancementCandidate[] }> {
  return apiFetchAuthed(
    `/projects/${projectId}/idea/enhancement-candidates`,
  );
}

export function requestIdeaEnhancement(
  projectId: string,
  reviewerUserIds: string[],
): Promise<{ status: string; newly_assigned_user_ids: string[] }> {
  return apiFetchAuthed(`/projects/${projectId}/idea/request-enhancement`, {
    method: "POST",
    body: { reviewer_user_ids: reviewerUserIds } as unknown as BodyInit,
  });
}
