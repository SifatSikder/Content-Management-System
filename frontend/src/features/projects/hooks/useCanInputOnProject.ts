"use client";

import { useEffect, useState } from "react";

import { useAuth } from "@/features/auth/hooks/useAuth";
import { listStageAssignees } from "@/features/projects/api";
import type { Project } from "@/features/projects/types";

/**
 * Compute whether the current user can take input actions on this
 * project, per the rule:
 *
 *   * Project owner (typically the Assistant CEO who created it) →
 *     always editable.
 *   * Anyone else → editable only while they're an active assignee on
 *     the project's CURRENT stage.
 *
 * Returns `null` while loading (so callers can hide affordances during
 * the brief fetch window), then `true` or `false`.
 */
export function useCanInputOnProject(project: Project | null): boolean | null {
  const auth = useAuth();
  const userId = auth.user?.id ?? null;
  const isOwner =
    userId !== null && project !== null && project.owner_id === userId;
  const [isAssignee, setIsAssignee] = useState<boolean | null>(null);

  const projectId = project?.id ?? null;
  const stageKey = project?.stage_key ?? null;

  useEffect(() => {
    if (!userId || !projectId || !stageKey || isOwner) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await listStageAssignees(projectId, stageKey);
        if (cancelled) return;
        setIsAssignee(res.items.some((a) => a.user_id === userId));
      } catch {
        if (cancelled) return;
        setIsAssignee(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId, stageKey, userId, isOwner]);

  if (project === null) return null;
  if (isOwner) return true;
  if (userId === null) return false;
  return isAssignee;
}
