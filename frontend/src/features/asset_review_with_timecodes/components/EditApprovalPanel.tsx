"use client";

import { CheckCircle2 } from "lucide-react";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import type { EditApprovalSummary } from "@/features/asset_review_with_timecodes/types";

interface Props {
  summary: EditApprovalSummary | null;
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
 * Pure render of the per-required-reviewer approval roster for the
 * current cut. The Approve button + summary fetch live in the parent
 * EditsTab so the action bar can coordinate with the Send-issues
 * button (mutually exclusive controls).
 */
export function EditApprovalPanel({ summary }: Props) {
  if (summary === null) {
    return <p className="text-muted-foreground text-sm">Loading approvals…</p>;
  }

  if (summary.required_reviewers.length === 0) {
    return (
      <p className="text-muted-foreground text-sm">
        No approvers configured for this department.
      </p>
    );
  }

  const approvalByReviewer = new Map(
    summary.approvals.map((a) => [a.reviewer_id, a] as const),
  );

  return (
    <ul className="divide-border divide-y rounded-md border">
      {summary.required_reviewers.map((reviewer) => {
        const approval = approvalByReviewer.get(reviewer.user_id);
        return (
          <li key={reviewer.user_id} className="flex items-center gap-3 p-3">
            <Avatar className="size-8">
              {reviewer.avatar_url ? (
                <AvatarImage src={reviewer.avatar_url} alt={reviewer.name} />
              ) : null}
              <AvatarFallback className="text-xs">
                {initials(reviewer.name)}
              </AvatarFallback>
            </Avatar>
            <div className="min-w-0 flex-1 space-y-0.5">
              <div className="flex items-center gap-2">
                <span className="truncate text-sm font-medium">
                  {reviewer.name}
                </span>
                <span className="text-muted-foreground text-xs">
                  {reviewer.role_label}
                </span>
                {approval ? (
                  <Badge variant="default" className="gap-1 text-[10px]">
                    <CheckCircle2 className="size-3" />
                    Approved
                  </Badge>
                ) : (
                  <Badge variant="outline" className="text-[10px]">
                    Awaiting
                  </Badge>
                )}
              </div>
              {approval ? (
                <p className="text-muted-foreground text-xs">
                  {new Date(approval.created_at).toLocaleString()}
                </p>
              ) : null}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
