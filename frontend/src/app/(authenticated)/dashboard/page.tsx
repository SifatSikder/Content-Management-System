"use client";

import { useTranslations } from "next-intl";

import { AwaitingTile } from "@/features/dashboard/components/AwaitingTile";
import { StageHistogram } from "@/features/dashboard/components/StageHistogram";
import { StuckList } from "@/features/dashboard/components/StuckList";
import { ThroughputChart } from "@/features/dashboard/components/ThroughputChart";
import { TimeInStageTable } from "@/features/dashboard/components/TimeInStageTable";

export default function DashboardPage() {
  const t = useTranslations("dashboard");
  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">{t("page_title")}</h1>
        <p className="text-muted-foreground text-sm">{t("page_subtitle")}</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <AwaitingTile />
        <StuckList days={5} />
      </div>

      <StageHistogram />

      <div className="grid gap-6 lg:grid-cols-2">
        <ThroughputChart weeks={12} />
        <TimeInStageTable />
      </div>
    </div>
  );
}
