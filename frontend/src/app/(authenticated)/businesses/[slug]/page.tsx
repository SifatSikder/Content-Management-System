"use client";

import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { useBusinesses } from "@/features/businesses/hooks/useBusinesses";
import { DepartmentList } from "@/features/departments/components/DepartmentList";

/**
 * Single business landing page — just the department list. Members are
 * managed per-department now (a person belongs to a department, not to
 * a business as a whole — the business membership is auto-derived from
 * their department assignments).
 */
export default function BusinessDashboardPage() {
  const t = useTranslations("businesses");
  const params = useParams<{ slug: string }>();
  const auth = useAuth();
  const { status, items } = useBusinesses();

  const business = items.find((b) => b.slug === params.slug);

  if (status === "loading") {
    return (
      <div className="mx-auto w-full max-w-5xl space-y-4 p-6">
        <Skeleton className="h-8 w-1/3" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (!business) {
    return (
      <div className="mx-auto w-full max-w-5xl p-6">
        <Card>
          <CardHeader>
            <CardTitle>{t("not_found")}</CardTitle>
          </CardHeader>
          <CardContent>{t("not_found_body")}</CardContent>
        </Card>
      </div>
    );
  }

  const canEdit = auth.user?.is_super_admin || business.is_owner;

  return (
    <div className="mx-auto w-full max-w-5xl space-y-8 p-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">{business.name}</h1>
      </header>
      <DepartmentList
        businessId={business.id}
        businessSlug={business.slug}
        canEdit={canEdit}
      />
    </div>
  );
}
