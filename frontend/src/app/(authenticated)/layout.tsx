"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/features/auth/hooks/useAuth";

export default function AuthenticatedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const auth = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (auth.status === "anonymous") {
      router.replace("/");
      return;
    }
    // Force users who need to change password through /change-password first.
    // Exempt the page itself to avoid infinite redirect.
    if (
      auth.status === "authenticated" &&
      auth.user?.must_change_password &&
      pathname !== "/change-password"
    ) {
      router.replace("/change-password");
    }
  }, [auth.status, auth.user, pathname, router]);

  // Always render a stable wrapper. Conditional `return null` then re-mount
  // was the source of a React 19 removeChild error: when `useSession()` flips
  // status from "loading" → "authenticated", a `null`-then-tree swap forces
  // the entire subtree (including children with portals) to unmount + mount
  // in the same commit, and Radix/Sonner portals get tangled in the process.
  const ready = auth.status === "authenticated" && auth.user !== null;

  return (
    <div className="flex min-h-screen flex-col">
      {ready && auth.user ? (
        <AppShell user={auth.user}>{children}</AppShell>
      ) : (
        <div className="flex flex-1 items-center justify-center p-6">
          <div className="w-full max-w-md space-y-3">
            <Skeleton className="h-6 w-1/3" />
            <Skeleton className="h-32 w-full" />
          </div>
        </div>
      )}
    </div>
  );
}
