"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { fetchStages } from "@/features/dashboard/api";
import type { StageCount } from "@/features/dashboard/types";
import { useStageLabel } from "@/features/departments/hooks/useStageLabel";

interface Props {
  departmentId: string;
}

export function StageHistogram({ departmentId }: Props) {
  const t = useTranslations("dashboard");
  const stageLabel = useStageLabel(departmentId);
  const [data, setData] = useState<StageCount[] | null>(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    fetchStages(departmentId).then(setData).catch(() => setErr(true));
  }, [departmentId]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("stages_title")}</CardTitle>
        <CardDescription>{t("stages_description")}</CardDescription>
      </CardHeader>
      <CardContent>
        {err && <p className="text-destructive text-sm">{t("load_failed")}</p>}
        {data === null && !err && (
          <p className="text-muted-foreground text-sm">{t("loading")}</p>
        )}
        {data !== null && (
          <div className="h-[280px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={data.map((row) => ({
                  ...row,
                  label: stageLabel(row.stage),
                }))}
                margin={{ top: 8, right: 16, left: 0, bottom: 48 }}
              >
                <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                <XAxis
                  dataKey="label"
                  angle={-35}
                  textAnchor="end"
                  interval={0}
                  height={64}
                  tick={{ fontSize: 11 }}
                />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip
                  cursor={{ fill: "rgba(0,0,0,0.04)" }}
                  contentStyle={{
                    background: "var(--popover)",
                    color: "var(--popover-foreground)",
                    borderRadius: 8,
                    border: "1px solid var(--border)",
                    fontSize: 12,
                  }}
                />
                <Bar dataKey="count" fill="var(--primary)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
