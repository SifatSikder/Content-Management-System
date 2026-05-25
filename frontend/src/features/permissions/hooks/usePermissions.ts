"use client";

import { useEffect, useState } from "react";

import { getMyPermissions } from "../api";
import type { DepartmentPermissions } from "../types";

type State = {
  data: DepartmentPermissions | null;
  loading: boolean;
  error: Error | null;
};

const INITIAL: State = { data: null, loading: false, error: null };

/**
 * Fetch (and cache in component state) the current user's permission map
 * for one department. The map is the single batched payload the kanban +
 * project tabs use to decide which affordances to render.
 *
 * Passing `null` or an empty department id is a no-op — useful while
 * `useCurrentDepartment` is still loading.
 */
export function usePermissions(departmentId: string | null | undefined): State {
  const [state, setState] = useState<State>(INITIAL);

  useEffect(() => {
    if (!departmentId) {
      setState(INITIAL);
      return;
    }
    let cancelled = false;
    setState((prev) => ({ ...prev, loading: true, error: null }));
    getMyPermissions(departmentId)
      .then((data) => {
        if (cancelled) return;
        setState({ data, loading: false, error: null });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setState({
          data: null,
          loading: false,
          error: err instanceof Error ? err : new Error(String(err)),
        });
      });
    return () => {
      cancelled = true;
    };
  }, [departmentId]);

  return state;
}

/**
 * Convenience predicate: returns true once the permission map is loaded and
 * the user is allowed to perform `actionKey` (or is a super-admin). Until
 * the map loads, returns `false` — UI affordances stay hidden during the
 * brief fetch window.
 */
export function useCanIDo(
  departmentId: string | null | undefined,
  actionKey: string,
): boolean {
  const { data } = usePermissions(departmentId);
  if (!data) return false;
  if (data.is_super_admin) return true;
  return data.allowed[actionKey] === true;
}
