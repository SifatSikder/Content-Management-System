"use client";

import { signOut as nextAuthSignOut, useSession } from "next-auth/react";

import type { AuthUser } from "@/features/auth/types";

export interface AuthState {
  status: "loading" | "authenticated" | "anonymous";
  user: AuthUser | null;
}

/**
 * Read-only auth state derived from the NextAuth session.
 *
 * Login/logout no longer go through this hook — login is via the Credentials
 * form posting to `/api/auth/callback/credentials` (handled by `signIn()` in
 * `next-auth/react`), and logout calls `signOut()` directly.
 */
export function useAuth(): AuthState & {
  logout: () => Promise<void>;
} {
  const { data, status } = useSession();

  const authStatus: AuthState["status"] =
    status === "loading" ? "loading" : status === "authenticated" ? "authenticated" : "anonymous";

  const user: AuthUser | null =
    data?.user && data.user.id
      ? {
          id: data.user.id,
          email: data.user.email ?? "",
          name: data.user.name ?? "",
          role: data.user.role,
          must_change_password: data.user.must_change_password,
          is_super_admin: Boolean(data.user.is_super_admin),
          image: data.user.image ?? null,
        }
      : null;

  return {
    status: authStatus,
    user,
    async logout() {
      await nextAuthSignOut({ redirect: false });
    },
  };
}
