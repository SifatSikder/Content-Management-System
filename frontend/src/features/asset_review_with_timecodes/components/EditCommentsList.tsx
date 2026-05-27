"use client";

import { useTranslations } from "next-intl";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  reopenEditComment,
  resolveEditComment,
} from "@/features/asset_review_with_timecodes/api";
import type { EditComment } from "@/features/asset_review_with_timecodes/types";

interface Props {
  comments: EditComment[];
  onUpdate: (c: EditComment) => void;
  onJumpTo: (seconds: number) => void;
  currentUserId: string;
  /** True only for the editor on this cut — reviewers post the
   *  feedback but the editor is the one who marks it addressed. */
  canResolve?: boolean;
}

function fmt(s: number): string {
  const total = Math.max(0, Math.floor(s));
  const m = Math.floor(total / 60);
  const sec = total % 60;
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

export function EditCommentsList({
  comments,
  onUpdate,
  onJumpTo,
  currentUserId,
  canResolve = false,
}: Props) {
  const t = useTranslations("edits");
  const tScript = useTranslations("script");
  const tToast = useTranslations("toast");
  const tErr = useTranslations("errors");

  async function toggle(c: EditComment) {
    try {
      const updated = c.resolved_at
        ? await reopenEditComment(c.id)
        : await resolveEditComment(c.id);
      onUpdate(updated);
      toast.success(updated.resolved_at ? tToast("comment_resolved") : tToast("comment_reopened"));
    } catch {
      toast.error(tErr("generic"));
    }
  }

  const sorted = [...comments].sort((a, b) => a.timestamp_seconds - b.timestamp_seconds);

  if (sorted.length === 0) {
    return <p className="text-muted-foreground py-4 text-center text-sm">{t("no_comments")}</p>;
  }

  return (
    <ul className="divide-y">
      {sorted.map((c) => {
        const isDraft = c.sent_at === null;
        const isMine = c.author_id === currentUserId;
        return (
          <li key={c.id} className="flex items-start gap-3 px-2 py-2 text-sm">
            <button
              type="button"
              onClick={() => onJumpTo(c.timestamp_seconds)}
              className="text-primary w-12 shrink-0 text-left text-xs tabular-nums hover:underline"
            >
              {fmt(c.timestamp_seconds)}
            </button>
            <span
              className={`flex-1 ${
                c.resolved_at ? "text-muted-foreground line-through" : ""
              }`}
            >
              {c.body}
            </span>
            {isDraft && isMine ? (
              <Badge variant="outline" className="shrink-0 text-[10px]">
                Draft
              </Badge>
            ) : null}
            {canResolve && !isDraft ? (
              <Button size="sm" variant="ghost" onClick={() => toggle(c)}>
                {c.resolved_at ? tScript("reopen") : tScript("resolve")}
              </Button>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}
