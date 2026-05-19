"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  addComment,
  listComments,
  reopenComment,
  resolveComment,
} from "@/features/scripts/api";
import type { ScriptComment } from "@/features/scripts/types";

interface Props {
  versionId: string;
}

export function ScriptComments({ versionId }: Props) {
  const tScript = useTranslations("script");
  const tToast = useTranslations("toast");
  const tErr = useTranslations("errors");
  const [comments, setComments] = useState<ScriptComment[]>([]);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const list = await listComments(versionId);
      setComments(list);
    } catch {
      toast.error(tErr("generic"));
    } finally {
      setLoading(false);
    }
  }, [versionId, tErr]);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function submitNew() {
    if (!draft.trim()) return;
    try {
      const created = await addComment(versionId, draft.trim());
      setComments((prev) => [...prev, created]);
      setDraft("");
      toast.success(tToast("comment_added"));
    } catch {
      toast.error(tErr("generic"));
    }
  }

  async function toggle(comment: ScriptComment) {
    try {
      const updated = comment.resolved_at
        ? await reopenComment(comment.id)
        : await resolveComment(comment.id);
      setComments((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
      toast.success(updated.resolved_at ? tToast("comment_resolved") : tToast("comment_reopened"));
    } catch {
      toast.error(tErr("generic"));
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <Input
          placeholder={tScript("add_comment")}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void submitNew();
          }}
        />
        <Button onClick={submitNew} disabled={!draft.trim()}>
          {tScript("add_comment")}
        </Button>
      </div>
      {loading ? null : comments.length === 0 ? (
        <p className="text-muted-foreground text-xs">—</p>
      ) : (
        <ul className="space-y-2">
          {comments.map((c) => (
            <li
              key={c.id}
              className="bg-muted/20 flex items-start justify-between gap-3 rounded-md border p-2 text-sm"
            >
              <span className={c.resolved_at ? "text-muted-foreground line-through" : ""}>
                {c.body}
              </span>
              <Button size="sm" variant="ghost" onClick={() => toggle(c)}>
                {c.resolved_at ? tScript("reopen") : tScript("resolve")}
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
