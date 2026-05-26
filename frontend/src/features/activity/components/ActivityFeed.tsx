"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { listProjectActivity } from "@/features/activity/api";
import { actionMessageKey, type ActivityItem } from "@/features/activity/types";
import { useStageLabel } from "@/features/departments/hooks/useStageLabel";

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString();
}

interface Props {
  projectId: string;
  /**
   * Department id for the project. Used by `useStageLabel` to render
   * stage-key metadata (e.g. `from: "draft_idea", to: "script_drafting"` on
   * `project.stage_changed` rows) as the localized stage names ("Draft idea"
   * → "Script drafting") instead of raw keys.
   */
  departmentId?: string;
}

export function ActivityFeed({ projectId, departmentId }: Props) {
  const t = useTranslations("activity");
  const tCommon = useTranslations("common");
  const stageLabel = useStageLabel(departmentId);
  const [items, setItems] = useState<ActivityItem[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "loading_more" | "error">(
    "loading",
  );

  const loadFirst = useCallback(async () => {
    setStatus("loading");
    try {
      const resp = await listProjectActivity(projectId, { limit: 25 });
      setItems(resp.items);
      setCursor(resp.next_cursor);
      setStatus("ready");
    } catch {
      setStatus("error");
    }
  }, [projectId]);

  const loadMore = useCallback(async () => {
    if (!cursor) return;
    setStatus("loading_more");
    try {
      const resp = await listProjectActivity(projectId, { cursor, limit: 25 });
      setItems((prev) => [...prev, ...resp.items]);
      setCursor(resp.next_cursor);
      setStatus("ready");
    } catch {
      setStatus("error");
    }
  }, [projectId, cursor]);

  useEffect(() => {
    void loadFirst();
  }, [loadFirst]);

  if (status === "loading") {
    return (
      <div className="space-y-2 p-4">
        {[...Array(5)].map((_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="space-y-3 p-4">
        <p className="text-muted-foreground text-sm">{tCommon("error")}</p>
        <Button variant="outline" onClick={() => loadFirst()}>
          {tCommon("retry")}
        </Button>
      </div>
    );
  }

  if (items.length === 0) {
    return <p className="text-muted-foreground p-4 text-sm">{tCommon("empty")}</p>;
  }

  return (
    <div className="divide-y">
      <ul>
        {items.map((item) => {
          const key = actionMessageKey(item.action);
          const verb = (() => {
            try {
              return t(key as Parameters<typeof t>[0]);
            } catch {
              return item.action;
            }
          })();
          // For stage transitions, render "from {Stage A} to {Stage B}" via
          // useStageLabel. Both `from` and `to` in metadata are stage *keys*
          // (e.g. "draft_idea") — useStageLabel resolves them to localized names.
          const transition = (() => {
            if (item.action !== "project.stage_changed") return null;
            const meta = item.metadata_json as { from?: string; to?: string };
            if (!meta.from && !meta.to) return null;
            return {
              from: meta.from ? stageLabel(meta.from) : null,
              to: meta.to ? stageLabel(meta.to) : null,
            };
          })();
          const actorName = item.actor?.name ?? "system";
          return (
            <li key={item.id} className="flex flex-col gap-1 px-4 py-3 text-sm">
              <span>
                <span className="font-medium">{actorName}</span>{" "}
                <span className="text-muted-foreground">
                  {verb}
                  {transition && (
                    <>
                      {transition.from && (
                        <>
                          {" "}
                          {t("from")}{" "}
                          <span className="text-foreground">{transition.from}</span>
                        </>
                      )}
                      {transition.to && (
                        <>
                          {" "}
                          {t("to")}{" "}
                          <span className="text-foreground">{transition.to}</span>
                        </>
                      )}
                    </>
                  )}
                </span>
              </span>
              <span className="text-muted-foreground text-xs">
                {formatDateTime(item.created_at)}
              </span>
            </li>
          );
        })}
      </ul>
      {cursor && (
        <div className="p-3 text-center">
          <Button
            variant="outline"
            size="sm"
            disabled={status === "loading_more"}
            onClick={() => loadMore()}
          >
            {t("load_more")}
          </Button>
        </div>
      )}
    </div>
  );
}
