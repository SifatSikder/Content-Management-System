"use client";

import { Building2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect } from "react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { useBusinesses } from "@/features/businesses/hooks/useBusinesses";
import { ATLAS_BUSINESS_COOKIE } from "@/features/businesses/hooks/useCurrentBusiness";

/**
 * Onboarding screen for users with zero business memberships. CEO super-
 * admins skip this (the middleware doesn't redirect them) and land on
 * `/projects` directly.
 */
export default function SelectBusinessPage() {
  const t = useTranslations("businesses");
  const router = useRouter();
  const auth = useAuth();
  const { status, items: businesses } = useBusinesses();

  // If the user is the CEO or already has a business pinned in cookie/state,
  // bounce them out — they shouldn't be here.
  useEffect(() => {
    if (auth.user?.is_super_admin) {
      router.replace("/projects");
    }
  }, [auth.user, router]);

  function pick(id: string) {
    // Single full-page navigation: set the cookie, then hard-redirect to
    // /projects. Using router.replace + location.reload races and one of
    // them aborts, leaving the user stuck on this page.
    document.cookie = `${ATLAS_BUSINESS_COOKIE}=${encodeURIComponent(id)}; path=/; max-age=${60 * 60 * 24 * 365}; SameSite=Lax`;
    window.location.href = "/projects";
  }

  return (
    <div className="mx-auto flex min-h-[60vh] w-full max-w-md flex-col justify-center p-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Building2 className="size-5" />
            {t("select_title")}
          </CardTitle>
          <CardDescription>{t("select_subtitle")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {status === "loading" ? (
            <Skeleton className="h-24 w-full" />
          ) : businesses.length === 0 ? (
            <p className="text-muted-foreground text-sm">{t("select_empty")}</p>
          ) : (
            businesses.map((b) => (
              <Button
                key={b.id}
                variant="outline"
                className="w-full justify-start"
                onClick={() => pick(b.id)}
              >
                {b.name}
              </Button>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}
