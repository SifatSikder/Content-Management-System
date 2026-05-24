"use client";

import { useCallback, useEffect, useState } from "react";

import { useBusinesses } from "@/features/businesses/hooks/useBusinesses";
import type { MeBusinessEntry } from "@/features/businesses/types";

/** Cookie that pins the user's "active" business across requests. */
export const ATLAS_BUSINESS_COOKIE = "atlas.business";

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const prefix = `${name}=`;
  const found = document.cookie
    .split(";")
    .map((c) => c.trim())
    .find((c) => c.startsWith(prefix));
  return found ? decodeURIComponent(found.slice(prefix.length)) : null;
}

function writeCookie(name: string, value: string): void {
  if (typeof document === "undefined") return;
  // 1-year max-age. Lax SameSite so middleware sees it on top-level navs.
  document.cookie = `${name}=${encodeURIComponent(value)}; path=/; max-age=${60 * 60 * 24 * 365}; SameSite=Lax`;
}

interface UseCurrentBusinessState {
  status: "loading" | "ready" | "none";
  current: MeBusinessEntry | null;
  businesses: MeBusinessEntry[];
  setCurrent: (id: string) => void;
  reload: () => Promise<void>;
}

/**
 * Resolves the user's currently-selected business from the `atlas.business`
 * cookie, falling back to the first membership in the list. Writing the
 * cookie triggers a full reload so the next API request goes out with the
 * new `X-Business-Id` header (set by `lib/api-client.ts`).
 */
export function useCurrentBusiness(): UseCurrentBusinessState {
  const { status: listStatus, items, reload } = useBusinesses();
  const [currentId, setCurrentId] = useState<string | null>(null);

  useEffect(() => {
    if (listStatus !== "ready") return;
    const cookieId = readCookie(ATLAS_BUSINESS_COOKIE);
    if (cookieId && items.some((b) => b.id === cookieId)) {
      setCurrentId(cookieId);
      return;
    }
    const first = items[0]?.id ?? null;
    setCurrentId(first);
    if (first) writeCookie(ATLAS_BUSINESS_COOKIE, first);
  }, [listStatus, items]);

  const setCurrent = useCallback((id: string) => {
    writeCookie(ATLAS_BUSINESS_COOKIE, id);
    setCurrentId(id);
    // Forces every cached useState/useEffect feature to re-fetch under the
    // new business context. Cheaper than threading a "businessVersion"
    // counter through every feature slice.
    if (typeof window !== "undefined") window.location.reload();
  }, []);

  const current = items.find((b) => b.id === currentId) ?? null;
  const resolvedStatus: UseCurrentBusinessState["status"] =
    listStatus === "loading"
      ? "loading"
      : items.length === 0
        ? "none"
        : "ready";

  return {
    status: resolvedStatus,
    current,
    businesses: items,
    setCurrent,
    reload,
  };
}
