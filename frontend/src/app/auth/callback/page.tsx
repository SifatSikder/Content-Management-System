"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { verifyToken } from "@/features/auth/api";
import { loginWithToken } from "@/features/auth/hooks/useAuth";

type Phase = "verifying" | "failed" | "redirecting";

export default function AuthCallbackPage() {
  const tAuth = useTranslations("auth");
  const router = useRouter();
  const params = useSearchParams();
  const token = params.get("token");
  const [phase, setPhase] = useState<Phase>("verifying");

  useEffect(() => {
    let cancelled = false;
    async function run() {
      if (!token) {
        setPhase("failed");
        return;
      }
      try {
        const { access_token } = await verifyToken(token);
        if (cancelled) return;
        loginWithToken(access_token);
        setPhase("redirecting");
        router.replace("/projects");
      } catch {
        if (!cancelled) setPhase("failed");
      }
    }
    void run();
    return () => {
      cancelled = true;
    };
  }, [token, router]);

  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-6 py-16">
      <Card>
        <CardHeader>
          <CardTitle>
            {phase === "failed" ? tAuth("verify_failed") : tAuth("verifying")}
          </CardTitle>
          {phase === "failed" && (
            <CardDescription>{tAuth("verify_failed_body")}</CardDescription>
          )}
        </CardHeader>
        <CardContent className="space-y-3">
          {phase !== "failed" ? (
            <>
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-5/6" />
            </>
          ) : (
            <Button onClick={() => router.replace("/")} variant="outline" className="w-full">
              {tAuth("send_again")}
            </Button>
          )}
        </CardContent>
      </Card>
    </main>
  );
}
