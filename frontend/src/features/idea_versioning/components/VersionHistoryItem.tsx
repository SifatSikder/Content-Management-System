"use client";

import { CheckCircle2, ChevronDown, ChevronRight, MessageCircleMore } from "lucide-react";
import { useState } from "react";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { listIdeaVersionSignoffs } from "@/features/idea_versioning/api";
import type { IdeaSignoff, IdeaVersion } from "@/features/idea_versioning/types";

interface Props {
  projectId: string;
  version: IdeaVersion;
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() ?? "")
    .join("");
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString();
}

export function VersionHistoryItem({ projectId, version }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [signoffs, setSignoffs] = useState<IdeaSignoff[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function toggle() {
    const next = !expanded;
    setExpanded(next);
    if (next && signoffs === null && !loading) {
      setLoading(true);
      setError(null);
      try {
        const rows = await listIdeaVersionSignoffs(projectId, version.id);
        setSignoffs(rows);
      } catch {
        setError("Failed to load feedback");
      } finally {
        setLoading(false);
      }
    }
  }

  // One row per reviewer — collapse multiple signoffs to the latest.
  const latestByReviewer = new Map<string, IdeaSignoff>();
  if (signoffs) {
    const sorted = [...signoffs].sort((a, b) =>
      a.created_at < b.created_at ? -1 : 1,
    );
    for (const s of sorted) {
      latestByReviewer.set(s.reviewer_id, s);
    }
  }

  return (
    <li className="text-xs">
      <button
        type="button"
        onClick={() => void toggle()}
        className="hover:bg-muted/50 flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left"
      >
        <span className="flex items-center gap-2">
          {expanded ? (
            <ChevronDown className="text-muted-foreground size-3" />
          ) : (
            <ChevronRight className="text-muted-foreground size-3" />
          )}
          <span className="font-medium">V{version.version_number}</span>
        </span>
        <span className="text-muted-foreground">
          {formatDate(version.created_at)}
        </span>
      </button>

      {expanded ? (
        <div className="space-y-3 px-4 pt-2 pb-3">
          <pre className="bg-muted/40 max-h-60 overflow-auto rounded-md p-3 text-sm whitespace-pre-wrap">
            {version.body_markdown}
          </pre>

          {loading ? (
            <p className="text-muted-foreground">Loading feedback…</p>
          ) : error ? (
            <p className="text-destructive">{error}</p>
          ) : latestByReviewer.size === 0 ? (
            <p className="text-muted-foreground">No feedback on this version.</p>
          ) : (
            <ul className="divide-border divide-y rounded-md border">
              {Array.from(latestByReviewer.values()).map((s) => {
                const name = s.reviewer_name ?? "Unknown reviewer";
                return (
                  <li key={s.id} className="flex items-start gap-3 p-2">
                    <Avatar className="size-7">
                      {s.reviewer_avatar_url ? (
                        <AvatarImage src={s.reviewer_avatar_url} alt={name} />
                      ) : null}
                      <AvatarFallback className="text-[10px]">
                        {initials(name)}
                      </AvatarFallback>
                    </Avatar>
                    <div className="min-w-0 flex-1 space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="truncate font-medium">{name}</span>
                        <Badge
                          variant={
                            s.decision === "looks_good"
                              ? "default"
                              : "destructive"
                          }
                          className="gap-1 text-[10px]"
                        >
                          {s.decision === "looks_good" ? (
                            <CheckCircle2 className="size-3" />
                          ) : (
                            <MessageCircleMore className="size-3" />
                          )}
                          {s.decision === "looks_good"
                            ? "Looks good"
                            : "Needs changes"}
                        </Badge>
                      </div>
                      {s.comment ? (
                        <p className="text-muted-foreground">
                          &ldquo;{s.comment}&rdquo;
                        </p>
                      ) : null}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      ) : null}
    </li>
  );
}
