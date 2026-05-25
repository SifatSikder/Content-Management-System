"use client";

import { ShieldOff } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";

import { ThemeToggle } from "@/components/layout/theme-toggle";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

/**
 * NextAuth redirects here (`pages.error = "/access-denied"`) whenever an
 * auth flow is denied — most commonly when an inactive user (their
 * `business_memberships.status == "revoked"`) completes a sign-in step
 * but the `signIn` callback rejects them. The page is intentionally
 * neutral about *why* — surfacing "your account is deactivated" reveals
 * account state to anyone who guessed an email correctly.
 */
export default function AccessDeniedPage() {
  const tApp = useTranslations("app");
  const t = useTranslations("access_denied");

  return (
    <div className="flex flex-1 flex-col">
      <header className="flex items-center justify-between border-b px-6 py-4">
        <span className="text-base font-semibold tracking-tight">{tApp("name")}</span>
        <ThemeToggle />
      </header>

      <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-6 py-16">
        <Card>
          <CardHeader className="items-center text-center">
            <div className="bg-muted text-muted-foreground mb-2 flex size-12 items-center justify-center rounded-full">
              <ShieldOff className="size-6" />
            </div>
            <CardTitle>{t("title")}</CardTitle>
            <CardDescription>{t("subtitle")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-muted-foreground text-sm">{t("body")}</p>
            <Button asChild className="w-full">
              <Link href="/">{t("back_to_sign_in")}</Link>
            </Button>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
