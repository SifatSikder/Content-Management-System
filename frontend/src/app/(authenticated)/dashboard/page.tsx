"use client";

import { useTranslations } from "next-intl";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function DashboardPage() {
  const t = useTranslations("shell");
  return (
    <div className="p-6">
      <Card>
        <CardHeader>
          <CardTitle>{t("dashboard")}</CardTitle>
          <CardDescription>Phase 3 wires this surface end-to-end.</CardDescription>
        </CardHeader>
        <CardContent className="text-muted-foreground text-sm">
          Stage histogram, awaiting-approval queue, throughput chart land in Task 3.4.
        </CardContent>
      </Card>
    </div>
  );
}
