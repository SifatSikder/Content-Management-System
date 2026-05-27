"use client";

import { CheckCircle2, MessageCircleMore } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { listDepartmentMembers } from "@/features/departments/api";
import type { DepartmentMembership } from "@/features/departments/types";
import { useCanIDo } from "@/features/permissions/hooks/usePermissions";
import { createIdeaSignoff } from "@/features/idea_versioning/api";
import type { IdeaSignoff, SignoffDecision } from "@/features/idea_versioning/types";
import { listStageAssignees } from "@/features/projects/api";
import type { AssignmentPublic, Project } from "@/features/projects/types";
import { ApiError } from "@/lib/api-client";
import { useEffect } from "react";

interface Props {
  project: Project;
  versionId: string | null;
  signoffs: IdeaSignoff[];
  currentUserId: string;
  onSignoffAdded?: (s: IdeaSignoff) => void;
  // Bumped by the parent whenever the idea state may have changed —
  // e.g. after Request feedback removed an assignee. Without it the
  // reviewer roster fetch only runs once on mount and goes stale.
  refreshKey?: number;
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() ?? "")
    .join("");
}

/**
 * Renders one row per active draft_idea assignee: avatar, latest decision
 * (looks_good / needs_changes / pending), comment if any. If the current
 * user has the `idea_versioning.signoff` permission, they can post a
 * fresh signoff inline.
 */
export function SignoffPanel({
  project,
  versionId,
  signoffs,
  currentUserId,
  onSignoffAdded,
  refreshKey,
}: Props) {
  const canSignoff = useCanIDo(project.department_id, "idea_versioning.signoff");
  const [reviewers, setReviewers] = useState<AssignmentPublic[] | null>(null);
  const [members, setMembers] = useState<DepartmentMembership[] | null>(null);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [a, m] = await Promise.all([
          listStageAssignees(project.id, "draft_idea"),
          listDepartmentMembers(project.department_id),
        ]);
        if (cancelled) return;
        // The project owner is the author of the idea — she doesn't
        // sign off on her own draft. Only the reviewers she pulled in
        // via Request feedback show up here.
        setReviewers(a.items.filter((r) => r.user_id !== project.owner_id));
        setMembers(m.items);
      } catch {
        if (cancelled) return;
        setReviewers([]);
        setMembers([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [project.id, project.department_id, refreshKey]);

  // Latest signoff per reviewer (signoffs come ordered ASC by created_at).
  const latestByReviewer = new Map<string, IdeaSignoff>();
  for (const s of signoffs) {
    latestByReviewer.set(s.reviewer_id, s);
  }

  async function submit(decision: SignoffDecision) {
    if (!versionId) return;
    setBusy(true);
    try {
      const row = await createIdeaSignoff(project.id, versionId, {
        decision,
        comment: comment.trim() || undefined,
      });
      toast.success(
        decision === "looks_good" ? "Marked as looks good" : "Changes requested",
      );
      setComment("");
      onSignoffAdded?.(row);
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.message : "Failed to sign off",
      );
    } finally {
      setBusy(false);
    }
  }

  if (reviewers === null || members === null) {
    return <p className="text-muted-foreground text-sm">Loading reviewers…</p>;
  }

  if (reviewers.length === 0) {
    return (
      <p className="text-muted-foreground text-sm">
        No reviewers assigned to the Draft Idea stage yet.
      </p>
    );
  }

  const myPending =
    canSignoff &&
    versionId !== null &&
    reviewers.some((r) => r.user_id === currentUserId) &&
    latestByReviewer.get(currentUserId)?.decision !== "looks_good";

  return (
    <div className="space-y-4">
      <ul className="divide-border divide-y rounded-md border">
        {reviewers.map((r) => {
          const latest = latestByReviewer.get(r.user_id);
          return (
            <li key={r.id} className="flex items-start gap-3 p-3">
              <Avatar className="size-8">
                {r.user.avatar_url ? (
                  <AvatarImage src={r.user.avatar_url} alt={r.user.name} />
                ) : null}
                <AvatarFallback className="text-xs">
                  {initials(r.user.name)}
                </AvatarFallback>
              </Avatar>
              <div className="min-w-0 flex-1 space-y-1">
                <div className="flex items-center gap-2">
                  <span className="truncate text-sm font-medium">
                    {r.user.name}
                  </span>
                  {latest ? (
                    <Badge
                      variant={
                        latest.decision === "looks_good" ? "default" : "destructive"
                      }
                      className="gap-1 text-[10px]"
                    >
                      {latest.decision === "looks_good" ? (
                        <CheckCircle2 className="size-3" />
                      ) : (
                        <MessageCircleMore className="size-3" />
                      )}
                      {latest.decision === "looks_good"
                        ? "Looks good"
                        : "Needs changes"}
                    </Badge>
                  ) : (
                    <Badge variant="outline" className="text-[10px]">
                      Awaiting
                    </Badge>
                  )}
                </div>
                {latest?.comment ? (
                  <p className="text-muted-foreground text-xs">
                    &ldquo;{latest.comment}&rdquo;
                  </p>
                ) : null}
              </div>
            </li>
          );
        })}
      </ul>

      {myPending ? (
        <div className="space-y-2 rounded-md border p-3">
          <p className="text-xs font-medium">Your decision</p>
          <Textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Optional comment for the author…"
            rows={2}
          />
          <div className="flex gap-2">
            <Button
              size="sm"
              disabled={busy}
              onClick={() => void submit("looks_good")}
            >
              <CheckCircle2 className="size-4" />
              Looks good
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={busy}
              onClick={() => void submit("needs_changes")}
            >
              <MessageCircleMore className="size-4" />
              Needs changes
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
