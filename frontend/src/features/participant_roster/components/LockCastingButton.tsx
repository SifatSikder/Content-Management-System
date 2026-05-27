"use client";

import { Lock, LockOpen } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  lockProjectCasting,
  unlockProjectCasting,
} from "@/features/participant_roster/api";
import { useCanIDo } from "@/features/permissions/hooks/usePermissions";
import type { Project } from "@/features/projects/types";
import { ApiError } from "@/lib/api-client";

interface Props {
  project: Project;
  isOwner?: boolean;
  onLocked?: () => void;
}

/**
 * Lock / Unlock CTAs for the casting phase. Mirrors the Lock Idea +
 * Lock Script pattern:
 *   * Owner-only buttons (CEO/Director see only the status badge).
 *   * Lock advances `casting → shoot_schedule` and stamps the columns.
 *   * Unlock clears the columns and rolls the stage back IFF the
 *     project is still on `shoot_schedule` (the immediate next stage).
 */
export function LockCastingButton({ project, isOwner = false, onLocked }: Props) {
  const hasLockPerm = useCanIDo(project.department_id, "casting.lock");
  const canAct = hasLockPerm && isOwner;
  const [busy, setBusy] = useState(false);

  const locked = project.casting_locked_at !== null;

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

  async function handleUnlock() {
    setBusy(true);
    try {
      await unlockProjectCasting(project.id);
      toast.success("Casting unlocked — you can edit the cast again");
      onLocked?.();
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : "Failed to unlock casting";
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  }

  if (locked) {
    return (
      <div className="flex items-center gap-2">
        <Badge variant="secondary" className="gap-1">
          <Lock className="size-3" />
          Casting locked
        </Badge>
        {canAct ? (
          <Button
            variant="outline"
            size="sm"
            onClick={handleUnlock}
            disabled={busy}
            title="Reopen casting so you can edit the cast set"
          >
            <LockOpen className="size-3.5" />
            Unlock casting
          </Button>
        ) : null}
      </div>
    );
  }

  if (!canAct) return null;

  return (
    <Button onClick={handleLock} disabled={busy} size="sm">
      <Lock className="size-3.5" />
      Lock casting
    </Button>
  );
}
