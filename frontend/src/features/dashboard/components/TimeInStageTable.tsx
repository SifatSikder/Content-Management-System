"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { fetchTimeInStage } from "@/features/dashboard/api";
import type { TimeInStage } from "@/features/dashboard/types";
import { useStageLabel } from "@/features/departments/hooks/useStageLabel";

interface Props {
  departmentId: string;
}

function fmt(value: number | null): string {
  if (value === null) return "—";
  return value < 1 ? value.toFixed(2) : value.toFixed(1);
}

export function TimeInStageTable({ departmentId }: Props) {
  const t = useTranslations("dashboard");
  const stageLabel = useStageLabel(departmentId);
  const [rows, setRows] = useState<TimeInStage[] | null>(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    fetchTimeInStage(departmentId).then(setRows).catch(() => setErr(true));
  }, [departmentId]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("time_in_stage_title")}</CardTitle>
        <CardDescription>{t("time_in_stage_description")}</CardDescription>
      </CardHeader>
      <CardContent className="text-sm">
        {err && <p className="text-destructive">{t("load_failed")}</p>}
        {rows === null && !err && (
          <p className="text-muted-foreground">{t("loading")}</p>
        )}
        {rows !== null && (
          <table className="w-full text-left">
            <thead className="text-muted-foreground text-xs uppercase">
              <tr>
                <th className="pb-2">{t("col_stage")}</th>
                <th className="pb-2 text-right">{t("col_samples")}</th>
                <th className="pb-2 text-right">{t("col_avg_days")}</th>
                <th className="pb-2 text-right">{t("col_max_days")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.stage} className="border-t">
                  <td className="py-1.5">{stageLabel(row.stage)}</td>
                  <td className="py-1.5 text-right">{row.sample_size}</td>
                  <td className="py-1.5 text-right">{fmt(row.avg_days)}</td>
                  <td className="py-1.5 text-right">{fmt(row.max_days)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </CardContent>
    </Card>
  );
}
