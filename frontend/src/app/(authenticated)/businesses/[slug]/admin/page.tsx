"use client";

import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { BusinessAdmin } from "@/features/businesses/components/BusinessAdmin";
import { useBusinesses } from "@/features/businesses/hooks/useBusinesses";
import { DepartmentList } from "@/features/departments/components/DepartmentList";

export default function BusinessAdminPage() {
  const t = useTranslations("businesses");
  const params = useParams<{ slug: string }>();
  const router = useRouter();
  const auth = useAuth();
  const { status, items } = useBusinesses();
  const business = items.find((b) => b.slug === params.slug);

  // Client-side guard. The backend's `require_business_admin` is the real
  // enforcement — this is only here to spare the user a flash of forbidden
  // content. CEO super-admins bypass.
  useEffect(() => {
    if (auth.status !== "authenticated" || status !== "ready" || !business) return;
    const allowed = auth.user?.is_super_admin || business.is_owner;
    if (!allowed) router.replace(`/businesses/${business.slug}`);
  }, [auth.status, auth.user, business, router, status]);

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

  return (
    <div className="mx-auto w-full max-w-5xl space-y-8 p-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">
          {business.name} — {t("admin")}
        </h1>
        <p className="text-muted-foreground font-mono text-xs">{business.slug}</p>
      </header>
      <BusinessAdmin businessId={business.id} />
      <DepartmentList
        businessId={business.id}
        businessSlug={business.slug}
        canEdit
      />
    </div>
  );
}
