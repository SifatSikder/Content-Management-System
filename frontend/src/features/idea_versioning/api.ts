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
