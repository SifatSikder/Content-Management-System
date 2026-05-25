"use client";

import { useEffect, useState } from "react";

import { useCurrentBusiness } from "@/features/businesses/hooks/useCurrentBusiness";
import { listMyDepartments } from "@/features/departments/api";
import type { MeDepartmentEntry } from "@/features/departments/types";

type State = {
  status: "loading" | "ready" | "none";
  current: MeDepartmentEntry | null;
  departments: MeDepartmentEntry[];
};

const INITIAL: State = { status: "loading", current: null, departments: [] };

/**
 * Pick the user's "current" department within the current business.
 *
 * Phase B ships one department per business by default ("Content Creation"
 * inside Sons Real Estate) so we don't bother with a department-switcher
 * yet — just take the first one in creation order. Future phases can pin
 * the selection in an `atlas.department` cookie the same way
 * `useCurrentBusiness` pins the business.
 */
export function useCurrentDepartment(): State {
  const { current: business, status: businessStatus } = useCurrentBusiness();
  const [state, setState] = useState<State>(INITIAL);

  useEffect(() => {
    if (businessStatus === "loading") {
      setState({ status: "loading", current: null, departments: [] });
      return;
    }
    if (!business) {
      setState({ status: "none", current: null, departments: [] });
      return;
    }
    let cancelled = false;
    listMyDepartments(business.id)
      .then((res) => {
        if (cancelled) return;
        const items = res.items;
        setState({
          status: items.length === 0 ? "none" : "ready",
          current: items[0] ?? null,
          departments: items,
        });
      })
      .catch(() => {
        if (cancelled) return;
        setState({ status: "none", current: null, departments: [] });
      });
    return () => {
      cancelled = true;
    };
  }, [business, businessStatus]);

  return state;
}
