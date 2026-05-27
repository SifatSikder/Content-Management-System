"use client";

import { CheckCircle2, MessageCircleMore, Send } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import {
  type EnhancementCandidate,
  listEnhancementCandidates,
  requestIdeaEnhancement,
} from "@/features/idea_versioning/api";
import type { Project } from "@/features/projects/types";
import { ApiError } from "@/lib/api-client";

interface Props {
  project: Project;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onRequested?: () => void;
}

function roleLabel(roleKey: string): string {
  switch (roleKey) {
    case "ceo":
      return "CEO";
    case "director":
    case "junior_director":
      return "Director";
    default:
      return roleKey;
  }
}

export function RequestFeedbackDialog({
  project,
  open,
  onOpenChange,
  onRequested,
}: Props) {
  const [candidates, setCandidates] = useState<EnhancementCandidate[] | null>(
    null,
  );
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await listEnhancementCandidates(project.id);
        if (cancelled) return;
        setCandidates(res.items);
        // Default checked: everyone EXCEPT reviewers whose latest
        // signoff on this idea is already `looks_good`. They've
        // approved, so don't re-spam them — the owner can still tick
        // them manually if she actually wants to re-notify.
        setSelected(
          new Set(
            res.items
              .filter((c) => c.latest_decision !== "looks_good")
              .map((c) => c.user_id),
          ),
        );
      } catch {
        if (cancelled) return;
        setCandidates([]);
        toast.error("Failed to load reviewers");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, project.id]);

  function toggle(userId: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(userId)) next.delete(userId);
      else next.add(userId);
      return next;
    });
  }

  async function onConfirm() {
    if (selected.size === 0 || submitting) return;
    setSubmitting(true);
    try {
      const res = await requestIdeaEnhancement(
        project.id,
        Array.from(selected),
      );
      const n = res.newly_assigned_user_ids.length;
      toast.success(
        n > 0
          ? `Feedback requested — ${n} reviewer(s) notified by email`
          : "Reviewers were already assigned",
      );
      onRequested?.();
      onOpenChange(false);
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.message : "Failed to request feedback",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Request feedback</AlertDialogTitle>
          <AlertDialogDescription>
            Pick the people who should review the current draft. Each one
            gets added to the card and emailed.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="space-y-2">
          {candidates === null ? (
            <p className="text-muted-foreground text-sm">Loading…</p>
          ) : candidates.length === 0 ? (
            <p className="text-muted-foreground text-sm">
              No CEO or Director members to ask. Add one to the department
              first.
            </p>
          ) : (
            <ul className="divide-border divide-y rounded-md border">
              {candidates.map((c) => {
                const id = `req-${c.user_id}`;
                const checked = selected.has(c.user_id);
                return (
                  <li
                    key={c.user_id}
                    className="hover:bg-muted flex min-w-0 items-center gap-3 p-3"
                  >
                    <Checkbox
                      id={id}
                      checked={checked}
                      onCheckedChange={() => toggle(c.user_id)}
                      disabled={submitting}
                      className="shrink-0"
                    />
                    <Label
                      htmlFor={id}
                      className="flex min-w-0 flex-1 cursor-pointer flex-col"
                    >
                      <div className="flex min-w-0 items-center gap-2">
                        <span className="truncate text-sm font-medium">
                          {c.name}
                        </span>
                        {c.latest_decision === "looks_good" ? (
                          <Badge
                            variant="default"
                            className="shrink-0 gap-1 text-[10px]"
                          >
                            <CheckCircle2 className="size-3" />
                            Approved
                          </Badge>
                        ) : c.latest_decision === "needs_changes" ? (
                          <Badge
                            variant="destructive"
                            className="shrink-0 gap-1 text-[10px]"
                          >
                            <MessageCircleMore className="size-3" />
                            Asked for changes
                          </Badge>
                        ) : null}
                      </div>
                      <div className="text-muted-foreground truncate text-xs">
                        {c.email} · {roleLabel(c.role_key)}
                      </div>
                    </Label>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={submitting}>Cancel</AlertDialogCancel>
          <AlertDialogAction
            disabled={selected.size === 0 || submitting}
            onClick={(e) => {
              e.preventDefault();
              void onConfirm();
            }}
          >
            <Send className="size-4" />
            {submitting
              ? "Sending…"
              : `Notify ${selected.size} reviewer${selected.size === 1 ? "" : "s"}`}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
