"use client";

import { Plus, X } from "lucide-react";
import { useEffect, useState } from "react";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";
import { listDepartmentMembers } from "@/features/departments/api";
import type { DepartmentMembership } from "@/features/departments/types";
import { useCanIDo } from "@/features/permissions/hooks/usePermissions";
import {
  addStageAssignee,
  listStageAssignees,
  removeStageAssignee,
} from "@/features/projects/api";
import type { AssignmentPublic, Project } from "@/features/projects/types";
import { cn } from "@/lib/utils";

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() ?? "")
    .join("");
}

interface Props {
  project: Project;
  /** Compact mode renders a single overlapping-avatar strip for the kanban card. */
  compact?: boolean;
}

/**
 * Renders the active assignees on the project's current stage. Click to
 * open a popover for adding/removing people. Initial chip set falls back
 * to the project owner before the popover loads the real list, so the
 * card doesn't render an empty hole.
 */
export function StageAssigneesPopover({ project, compact = true }: Props) {
  const canEdit = useCanIDo(project.department_id, "project.edit");

  const [open, setOpen] = useState(false);
  const [assignees, setAssignees] = useState<AssignmentPublic[] | null>(null);
  const [members, setMembers] = useState<DepartmentMembership[] | null>(null);
  const [busy, setBusy] = useState(false);

  // Fetch the real assignee list + the department member roster the first
  // time the popover is opened (and re-fetch every open so it stays fresh).
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    (async () => {
      try {
        const [a, m] = await Promise.all([
          listStageAssignees(project.id, project.stage_key),
          listDepartmentMembers(project.department_id),
        ]);
        if (cancelled) return;
        setAssignees(a.items);
        setMembers(m.items);
      } catch {
        if (cancelled) return;
        setAssignees([]);
        setMembers([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, project.id, project.stage_key, project.department_id]);

  async function handleAdd(userId: string) {
    setBusy(true);
    try {
      const row = await addStageAssignee(project.id, project.stage_key, userId);
      setAssignees((prev) => {
        if (prev === null) return [row];
        if (prev.some((a) => a.user_id === userId)) return prev;
        return [...prev, row];
      });
    } finally {
      setBusy(false);
    }
  }

  async function handleRemove(userId: string) {
    setBusy(true);
    try {
      await removeStageAssignee(project.id, project.stage_key, userId);
      setAssignees((prev) =>
        prev === null ? prev : prev.filter((a) => a.user_id !== userId),
      );
    } finally {
      setBusy(false);
    }
  }

  // Visible chips: live assignees if loaded; otherwise fall back to owner.
  const chips =
    assignees ??
    [
      {
        id: "owner-fallback",
        project_id: project.id,
        stage_key: project.stage_key,
        user_id: project.owner_id,
        user: project.owner,
        slot_key: null,
        assigned_at: project.created_at,
        assigned_by: null,
      } as AssignmentPublic,
    ];

  const assignedIds = new Set(chips.map((a) => a.user_id));
  const candidates =
    members?.filter((m) => !assignedIds.has(m.user_id)) ?? [];

  const trigger = (
    <button
      type="button"
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
      }}
      onPointerDown={(e) => e.stopPropagation()}
      className={cn(
        "flex items-center gap-1 rounded-full transition-opacity",
        canEdit && "hover:opacity-80",
        !canEdit && "cursor-default",
      )}
      aria-label="Stage assignees"
    >
      <div className="flex -space-x-2">
        {chips.slice(0, 3).map((a) => (
          <Avatar
            key={a.id}
            className="border-background size-6 border-2"
            title={a.user.name}
          >
            {a.user.avatar_url ? (
              <AvatarImage src={a.user.avatar_url} alt={a.user.name} />
            ) : null}
            <AvatarFallback className="text-[10px]">
              {initials(a.user.name)}
            </AvatarFallback>
          </Avatar>
        ))}
        {chips.length > 3 ? (
          <div className="bg-muted text-muted-foreground border-background flex size-6 items-center justify-center rounded-full border-2 text-[10px]">
            +{chips.length - 3}
          </div>
        ) : null}
      </div>
      {!compact ? (
        <span className="text-muted-foreground truncate text-[11px]">
          {chips.length === 1 ? chips[0].user.name : `${chips.length} assignees`}
        </span>
      ) : null}
    </button>
  );

  if (!canEdit) return trigger;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>{trigger}</PopoverTrigger>
      <PopoverContent
        className="w-72 p-0"
        align="start"
        onPointerDown={(e) => e.stopPropagation()}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="border-b p-3">
          <div className="text-muted-foreground mb-2 text-[11px] font-medium tracking-wide uppercase">
            Assigned ({chips.length})
          </div>
          <ScrollArea className="max-h-40">
            <ul className="space-y-1">
              {chips.map((a) => (
                <li
                  key={a.id}
                  className="hover:bg-muted flex items-center gap-2 rounded-md p-1.5"
                >
                  <Avatar className="size-6">
                    {a.user.avatar_url ? (
                      <AvatarImage src={a.user.avatar_url} alt={a.user.name} />
                    ) : null}
                    <AvatarFallback className="text-[10px]">
                      {initials(a.user.name)}
                    </AvatarFallback>
                  </Avatar>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-xs font-medium">
                      {a.user.name}
                    </div>
                    {a.slot_key ? (
                      <div className="text-muted-foreground text-[10px]">
                        {a.slot_key}
                      </div>
                    ) : null}
                  </div>
                  <Button
                    size="icon"
                    variant="ghost"
                    className="size-6"
                    disabled={busy}
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      void handleRemove(a.user_id);
                    }}
                    aria-label={`Remove ${a.user.name}`}
                  >
                    <X className="size-3.5" />
                  </Button>
                </li>
              ))}
              {chips.length === 0 ? (
                <li className="text-muted-foreground p-2 text-xs">
                  No one assigned yet.
                </li>
              ) : null}
            </ul>
          </ScrollArea>
        </div>
        <div className="p-3">
          <div className="text-muted-foreground mb-2 text-[11px] font-medium tracking-wide uppercase">
            Add a member
          </div>
          {members === null ? (
            <div className="text-muted-foreground text-xs">Loading…</div>
          ) : candidates.length === 0 ? (
            <div className="text-muted-foreground text-xs">
              Everyone in this department is already assigned.
            </div>
          ) : (
            <ScrollArea className="max-h-40">
              <ul className="space-y-1">
                {candidates.map((m) => (
                  <li key={m.id}>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        void handleAdd(m.user_id);
                      }}
                      className="hover:bg-muted flex w-full items-center gap-2 rounded-md p-1.5 text-left"
                    >
                      <Avatar className="size-6">
                        {m.user.avatar_url ? (
                          <AvatarImage src={m.user.avatar_url} alt={m.user.name} />
                        ) : null}
                        <AvatarFallback className="text-[10px]">
                          {initials(m.user.name)}
                        </AvatarFallback>
                      </Avatar>
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-xs font-medium">
                          {m.user.name}
                        </div>
                        <div className="text-muted-foreground truncate text-[10px]">
                          {m.user.email}
                        </div>
                      </div>
                      <Plus className="text-muted-foreground size-3.5" />
                    </button>
                  </li>
                ))}
              </ul>
            </ScrollArea>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
