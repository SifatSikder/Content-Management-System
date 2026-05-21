"use client";

import { useTranslations } from "next-intl";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { PushSettings } from "@/features/push/components/PushSettings";

export default function SettingsPage() {
  const t = useTranslations("shell");
  const tRoles = useTranslations("roles");
  const auth = useAuth();
  if (!auth.user) return null;

  return (
    <div className="space-y-6 p-6">
      <Card>
        <CardHeader>
          <CardTitle>{t("profile")}</CardTitle>
          <CardDescription>{auth.user.email}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <div>
            <span className="text-muted-foreground">Name:</span> {auth.user.name}
          </div>
          <div>
            <span className="text-muted-foreground">Role:</span> {tRoles(auth.user.role)}
          </div>
        </CardContent>
      </Card>

      <PushSettings />
    </div>
  );
}
