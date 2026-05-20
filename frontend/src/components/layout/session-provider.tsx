"use client";

import { SessionProvider as NextAuthSessionProvider } from "next-auth/react";

/**
 * Thin wrapper so the root layout doesn't need to mark itself "use client"
 * just to instantiate the SessionProvider.
 */
export function SessionProvider({ children }: { children: React.ReactNode }) {
  return <NextAuthSessionProvider>{children}</NextAuthSessionProvider>;
}
