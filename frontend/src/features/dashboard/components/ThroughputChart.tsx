"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { fetchThroughput } from "@/features/dashboard/api";
import type { ThroughputBucket } from "@/features/dashboard/types";

function formatWeek(iso: string): string {
  const d = new Date(iso);
  return `${(d.getMonth() + 1).toString().padStart(2, "0")}-${d.getDate().toString().padStart(2, "0")}`;
}

interface Props {
  departmentId: string;
  weeks?: number;
}

export function ThroughputChart({ departmentId, weeks = 12 }: Props) {
  const t = useTranslations("dashboard");
  const [data, setData] = useState<ThroughputBucket[] | null>(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    fetchThroughput(departmentId, weeks).then(setData).catch(() => setErr(true));
  }, [departmentId, weeks]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("throughput_title")}</CardTitle>
        <CardDescription>{t("throughput_description", { weeks })}</CardDescription>
      </CardHeader>
      <CardContent>
        {err && <p className="text-destructive text-sm">{t("load_failed")}</p>}
        {data === null && !err && (
          <p className="text-muted-foreground text-sm">{t("loading")}</p>
        )}
        {data !== null && (
          <div className="h-[240px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={data.map((row) => ({ ...row, label: formatWeek(row.week_start) }))}
                margin={{ top: 8, right: 16, left: 0, bottom: 8 }}
              >
                <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                <XAxis dataKey="label" tick={{ fontSize: 11 }} />
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
                <Line
                  type="monotone"
                  dataKey="count"
                  stroke="var(--primary)"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
