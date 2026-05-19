"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { useAuth } from "@/features/auth/hooks/useAuth";

export default function AuthenticatedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const auth = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (auth.status === "anonymous") {
      router.replace("/");
    }
  }, [auth.status, router]);

  if (auth.status !== "authenticated" || !auth.user) {
    return null;
  }

  return <AppShell user={auth.user}>{children}</AppShell>;
}
