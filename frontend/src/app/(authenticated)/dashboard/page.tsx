"use client";

import { useTranslations } from "next-intl";

import { Skeleton } from "@/components/ui/skeleton";
import { useCurrentDepartment } from "@/features/departments/hooks/useCurrentDepartment";
import { AwaitingTile } from "@/features/dashboard/components/AwaitingTile";
import { StageHistogram } from "@/features/dashboard/components/StageHistogram";
import { StuckList } from "@/features/dashboard/components/StuckList";
import { ThroughputChart } from "@/features/dashboard/components/ThroughputChart";
import { TimeInStageTable } from "@/features/dashboard/components/TimeInStageTable";

export default function DashboardPage() {
  const t = useTranslations("dashboard");
  const department = useCurrentDepartment();

  if (department.status === "loading") {
    return (
      <div className="space-y-6 p-6">
        <Skeleton className="h-8 w-64" />
        <div className="grid gap-6 lg:grid-cols-2">
          <Skeleton className="h-48" />
          <Skeleton className="h-48" />
        </div>
      </div>
    );
  }

  if (department.status === "none" || !department.current) {
    return (
      <div className="p-6">
        <h1 className="text-2xl font-semibold">{t("page_title")}</h1>
        <p className="text-muted-foreground mt-2 text-sm">{t("page_subtitle")}</p>
      </div>
    );
  }

  const departmentId = department.current.id;

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">{t("page_title")}</h1>
        <p className="text-muted-foreground text-sm">{t("page_subtitle")}</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <AwaitingTile departmentId={departmentId} />
        <StuckList departmentId={departmentId} days={5} />
      </div>

      <StageHistogram departmentId={departmentId} />

      <div className="grid gap-6 lg:grid-cols-2">
        <ThroughputChart departmentId={departmentId} weeks={12} />
        <TimeInStageTable departmentId={departmentId} />
      </div>
    </div>
  );
}
