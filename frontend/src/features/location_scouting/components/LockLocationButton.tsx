"use client";

import { Lock } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { lockProjectLocation } from "@/features/location_scouting/api";
import { useCanIDo } from "@/features/permissions/hooks/usePermissions";
import type { Project } from "@/features/projects/types";
import { ApiError } from "@/lib/api-client";

interface Props {
  project: Project;
  onLocked?: () => void;
}

/**
 * Explicit "Lock Location" CTA — stamps `projects.location_locked_at/by`
 * and advances `location_scouting → draft_idea`. Hidden when the project
 * is already past `location_scouting` AND already has a lock stamp; in
 * that case the badge below renders instead.
 */
export function LockLocationButton({ project, onLocked }: Props) {
  const canLock = useCanIDo(project.department_id, "location.lock");
  const [busy, setBusy] = useState(false);

  const locked = project.location_locked_at !== null;
  const stillScouting = project.stage_key === "location_scouting";

  if (!canLock && !locked) return null;
  if (locked && !stillScouting) {
    return (
      <div className="text-muted-foreground flex items-center gap-2 text-xs">
        <Lock className="size-3.5" />
        <span>Location locked</span>
      </div>
    );
  }
  if (!canLock) return null;

  async function handleLock() {
    setBusy(true);
    try {
      await lockProjectLocation(project.id);
      toast.success("Location locked — project advanced to Draft Idea");
      onLocked?.();
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : "Failed to lock location";
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Button
      onClick={handleLock}
      disabled={busy}
      size="sm"
      variant={stillScouting ? "default" : "secondary"}
    >
      <Lock className="size-3.5" />
      Lock location
    </Button>
  );
}
