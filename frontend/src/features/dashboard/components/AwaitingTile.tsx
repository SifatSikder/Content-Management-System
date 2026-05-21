"use client";

import { Inbox } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { fetchAwaiting } from "@/features/dashboard/api";
import type { AwaitingItem } from "@/features/dashboard/types";

export function AwaitingTile() {
  const t = useTranslations("dashboard");
  const tStages = useTranslations("stages");
  const [items, setItems] = useState<AwaitingItem[] | null>(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    fetchAwaiting().then(setItems).catch(() => setErr(true));
  }, []);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Inbox className="size-5" />
          {t("awaiting_title")}
          {items !== null && (
            <Badge variant="secondary" className="ml-auto">
              {items.length}
            </Badge>
          )}
        </CardTitle>
        <CardDescription>{t("awaiting_description")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        {err && <p className="text-destructive">{t("load_failed")}</p>}
        {items === null && !err && (
          <p className="text-muted-foreground">{t("loading")}</p>
        )}
        {items !== null && items.length === 0 && (
          <p className="text-muted-foreground">{t("awaiting_empty")}</p>
        )}
        {items?.map((item) => (
          <Link
            key={item.cut_id}
            href={`/projects/${item.project_id}`}
            className="hover:bg-accent flex items-center justify-between gap-3 rounded-md border px-3 py-2"
          >
            <div className="min-w-0 flex-1">
              <div className="truncate font-medium">{item.project_title}</div>
              <div className="text-muted-foreground text-xs">
                {t("awaiting_cut_label", { n: item.cut_version })} ·{" "}
                {new Date(item.uploaded_at).toLocaleDateString()}
              </div>
            </div>
            <Badge variant="outline">{tStages(item.stage)}</Badge>
          </Link>
        ))}
      </CardContent>
    </Card>
  );
}
