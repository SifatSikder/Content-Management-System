"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { listProjectActivity } from "@/features/activity/api";
import { actionMessageKey, type ActivityItem } from "@/features/activity/types";

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString();
}

interface Props {
  projectId: string;
}

export function ActivityFeed({ projectId }: Props) {
  const t = useTranslations("activity");
  const tCommon = useTranslations("common");
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
          return (
            <li key={item.id} className="flex flex-col gap-1 px-4 py-3 text-sm">
              <span>
                <span className="font-medium">
                  {item.actor_id ? item.actor_id.slice(0, 8) : "system"}
                </span>{" "}
                <span className="text-muted-foreground">{verb}</span>
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
