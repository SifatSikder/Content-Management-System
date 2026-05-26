"use client";

import { useEffect, useState } from "react";

import { listMyDepartments } from "@/features/departments/api";
import { ATLAS_BUSINESS_COOKIE } from "@/features/businesses/hooks/useCurrentBusiness";

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const prefix = `${name}=`;
  const found = document.cookie
    .split(";")
    .map((c) => c.trim())
    .find((c) => c.startsWith(prefix));
  return found ? decodeURIComponent(found.slice(prefix.length)) : null;
}

/**
 * Returns the localized name of the current user's role in the currently
 * active business. If the user belongs to multiple departments in that
 * business with different roles, the first one (oldest department) wins —
 * which matches how `/me/departments` orders them.
 *
 * Returns `null` while loading, if no business is pinned, or if the user
 * has no department membership in the current business.
 */
export function useMyBusinessRole(locale = "en"): string | null {
  const [label, setLabel] = useState<string | null>(null);

  useEffect(() => {
    const businessId = readCookie(ATLAS_BUSINESS_COOKIE);
    if (!businessId) {
      setLabel(null);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const res = await listMyDepartments(businessId);
        if (cancelled) return;
        const first = res.items.find((d) => d.role_name_i18n);
        if (!first || !first.role_name_i18n) {
          setLabel(null);
          return;
        }
        const i18n = first.role_name_i18n;
        setLabel(i18n[locale] ?? i18n.en ?? i18n.nl ?? null);
      } catch {
        if (cancelled) return;
        setLabel(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [locale]);

  return label;
}
