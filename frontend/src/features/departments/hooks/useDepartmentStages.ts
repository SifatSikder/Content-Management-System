"use client";

import { useEffect, useState } from "react";

import { listStages } from "../api";
import type { Stage } from "../types";

type State = {
  stages: Stage[];
  loading: boolean;
  error: Error | null;
};

const INITIAL: State = { stages: [], loading: false, error: null };

/**
 * Fetch the ordered list of stages for one department.
 *
 * Returned stages are sorted by `order_index` ascending — the same order the
 * kanban renders them as columns. Passing `null` / `undefined` is a no-op
 * (useful while the project / current-department is still loading).
 */
export function useDepartmentStages(
  departmentId: string | null | undefined,
): State {
  const [state, setState] = useState<State>(INITIAL);

  useEffect(() => {
    if (!departmentId) {
      setState(INITIAL);
      return;
    }
    let cancelled = false;
    setState((prev) => ({ ...prev, loading: true, error: null }));
    listStages(departmentId)
      .then((res) => {
        if (cancelled) return;
        const sorted = [...res.items].sort((a, b) => a.order_index - b.order_index);
        setState({ stages: sorted, loading: false, error: null });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setState({
          stages: [],
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
