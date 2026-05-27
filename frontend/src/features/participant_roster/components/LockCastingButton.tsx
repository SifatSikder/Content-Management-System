"use client";

import { Lock } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { lockProjectCasting } from "@/features/participant_roster/api";
import { useCanIDo } from "@/features/permissions/hooks/usePermissions";
import type { Project } from "@/features/projects/types";
import { ApiError } from "@/lib/api-client";

interface Props {
  project: Project;
  isOwner?: boolean;
  onLocked?: () => void;
}

/**
 * Explicit "Lock Casting" CTA — stamps `projects.casting_locked_at/by`
 * and advances `casting → shoot_schedule`. Renders a static badge once
 * the project has moved past casting (visible to everyone). The
 * actionable button is owner-only — even if CEO/Director hold the
 * permission, only the Asst CEO decides when casting is done.
 */
export function LockCastingButton({ project, isOwner = false, onLocked }: Props) {
  const canLock = useCanIDo(project.department_id, "casting.lock") && isOwner;
  const [busy, setBusy] = useState(false);

  const locked = project.casting_locked_at !== null;
  const stillCasting = project.stage_key === "casting";

  if (!canLock && !locked) return null;
  if (locked && !stillCasting) {
    return (
      <div className="text-muted-foreground flex items-center gap-2 text-xs">
        <Lock className="size-3.5" />
        <span>Casting locked</span>
      </div>
    );
  }
  if (!canLock) return null;

  async function handleLock() {
    setBusy(true);
    try {
      await lockProjectCasting(project.id);
      toast.success("Casting locked — project advanced to Shoot schedule");
      onLocked?.();
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : "Failed to lock casting";
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
      variant={stillCasting ? "default" : "secondary"}
    >
      <Lock className="size-3.5" />
      Lock casting
    </Button>
  );
}
