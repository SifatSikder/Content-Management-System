"use client";

import { Building2, Plus } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { CreateBusinessDialog } from "@/features/businesses/components/CreateBusinessDialog";
import { useBusinesses } from "@/features/businesses/hooks/useBusinesses";

export default function BusinessesPage() {
  const t = useTranslations("businesses");
  const auth = useAuth();
  const { status, items, reload } = useBusinesses();
  const canCreate = auth.user?.is_super_admin ?? false;

  return (
    <div className="mx-auto w-full max-w-5xl space-y-6 p-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{t("page_title")}</h1>
          <p className="text-muted-foreground text-sm">{t("page_subtitle")}</p>
        </div>
        {canCreate ? (
          <CreateBusinessDialog
            trigger={
              <Button>
                <Plus className="mr-2 size-4" />
                {t("create_action")}
              </Button>
            }
            onCreated={() => void reload()}
          />
        ) : null}
      </header>

      {status === "loading" ? (
        <div className="grid gap-4 md:grid-cols-2">
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
        </div>
      ) : items.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>{t("none")}</CardTitle>
            <CardDescription>{t("none_subtitle")}</CardDescription>
          </CardHeader>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {items.map((b) => (
            <Link
              key={b.id}
              href={`/businesses/${b.slug}`}
              className="focus-visible:ring-ring rounded-xl focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none"
            >
              <Card className="hover:border-ring h-full transition-colors">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Building2 className="size-4" />
                    <span className="truncate">{b.name}</span>
                  </CardTitle>
                  <CardDescription className="font-mono text-xs">
                    {b.slug}
                  </CardDescription>
                </CardHeader>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
