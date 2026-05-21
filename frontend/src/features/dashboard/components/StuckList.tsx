"use client";

import { AlertTriangle } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { fetchStuck } from "@/features/dashboard/api";
import type { StuckProject } from "@/features/dashboard/types";

interface Props {
  days?: number;
}

export function StuckList({ days = 5 }: Props) {
  const t = useTranslations("dashboard");
  const tStages = useTranslations("stages");
  const [items, setItems] = useState<StuckProject[] | null>(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    fetchStuck(days).then(setItems).catch(() => setErr(true));
  }, [days]);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <AlertTriangle className="size-5 text-amber-500" />
          {t("stuck_title")}
          {items !== null && (
            <Badge variant="secondary" className="ml-auto">
              {items.length}
            </Badge>
          )}
        </CardTitle>
        <CardDescription>{t("stuck_description", { days })}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        {err && <p className="text-destructive">{t("load_failed")}</p>}
        {items === null && !err && (
          <p className="text-muted-foreground">{t("loading")}</p>
        )}
        {items !== null && items.length === 0 && (
          <p className="text-muted-foreground">{t("stuck_empty")}</p>
        )}
        {items?.map((item) => (
          <Link
            key={item.project_id}
            href={`/projects/${item.project_id}`}
            className="hover:bg-accent flex items-center justify-between gap-3 rounded-md border px-3 py-2"
          >
            <div className="min-w-0 flex-1">
              <div className="truncate font-medium">{item.project_title}</div>
              <div className="text-muted-foreground text-xs">
                {t("stuck_idle_for", { days: item.days_idle })} · {item.owner_name}
              </div>
            </div>
            <Badge variant="outline">{tStages(item.stage)}</Badge>
          </Link>
        ))}
      </CardContent>
    </Card>
  );
}
