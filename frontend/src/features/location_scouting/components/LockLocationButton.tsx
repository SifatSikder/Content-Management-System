"use client";

import { Lock, LockOpen } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/features/auth/hooks/useAuth";
import {
  lockProjectLocation,
  unlockProjectLocation,
} from "@/features/location_scouting/api";
import { useCanIDo } from "@/features/permissions/hooks/usePermissions";
import type { Project } from "@/features/projects/types";
import { ApiError } from "@/lib/api-client";

interface Props {
  project: Project;
  onChanged?: () => void;
}

/**
 * Lock / Unlock toggle for the Location set.
 *
 * - Not locked + can.lock → Lock button (stamps the columns; on
 *   `location_scouting` also advances the stage to `draft_idea`).
 * - Locked + can.lock → Unlock button (clears the columns; doesn't
 *   roll the stage back).
 * - Locked + can't.lock → static "Location locked" badge (for the
 *   CEO / Director who can see the project but not change it).
 */
export function LockLocationButton({ project, onChanged }: Props) {
  // Lock / Unlock is owner-only. Even the CEO super-admin (who would
  // otherwise pass every permission check) only sees the static badge
  // when the project belongs to someone else — they're a watcher here,
  // not the executive driver.
  const auth = useAuth();
  const isOwner = auth.user?.id === project.owner_id;
  const hasLockPerm = useCanIDo(project.department_id, "location.lock");
  const canLock = isOwner && hasLockPerm;
  const [busy, setBusy] = useState(false);

  const locked = project.location_locked_at !== null;

  if (locked && !canLock) {
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
      onChanged?.();
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : "Failed to lock location";
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  }

  async function handleUnlock() {
    setBusy(true);
    try {
      await unlockProjectLocation(project.id);
      toast.success("Location unlocked — you can edit again");
      onChanged?.();
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : "Failed to unlock location";
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  }

  if (locked) {
    return (
      <Button onClick={handleUnlock} disabled={busy} size="sm" variant="secondary">
        <LockOpen className="size-3.5" />
        Unlock location
      </Button>
    );
  }
  return (
    <Button onClick={handleLock} disabled={busy} size="sm">
      <Lock className="size-3.5" />
      Lock location
    </Button>
  );
}
