"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/lib/api-client";

import { listProjects, type ListProjectsParams } from "../api";
import type { Project } from "../types";

export interface UseProjectsResult {
  projects: Project[];
  status: "loading" | "ready" | "error";
  error: string | null;
  reload: () => Promise<void>;
  /** Apply an optimistic patch + roll back on failure. */
  optimisticUpdate: (
    id: string,
    patch: Partial<Project>,
    commit: () => Promise<Project | void>,
  ) => Promise<void>;
  /** Insert a freshly-created project at the top of the list. */
  prepend: (project: Project) => void;
}

// Must stay ≤ the backend's MAX_PAGE_SIZE (app/services/project_service.py).
const PAGE_LIMIT = 100;

export function useProjects(params: ListProjectsParams = {}): UseProjectsResult {
  const [projects, setProjects] = useState<Project[]>([]);
  const [status, setStatus] = useState<UseProjectsResult["status"]>("loading");
  const [error, setError] = useState<string | null>(null);
  const filterKey = JSON.stringify(params);

  const reload = useCallback(async () => {
    setStatus("loading");
    setError(null);
    try {
      const resp = await listProjects({ ...params, limit: PAGE_LIMIT });
      setProjects(resp.items);
      setStatus("ready");
    } catch (err) {
      setStatus("error");
      setError(err instanceof ApiError ? err.message : "load_error");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterKey]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const optimisticUpdate = useCallback(
    async (id: string, patch: Partial<Project>, commit: () => Promise<Project | void>) => {
      let snapshot: Project[] = [];
      setProjects((prev) => {
        snapshot = prev;
        return prev.map((p) => (p.id === id ? { ...p, ...patch } : p));
      });
      try {
        const updated = await commit();
        if (updated) {
          setProjects((prev) => prev.map((p) => (p.id === id ? updated : p)));
        }
      } catch (err) {
        setProjects(snapshot);
        throw err;
      }
    },
    [],
  );

  const prepend = useCallback((project: Project) => {
    setProjects((prev) => [project, ...prev]);
  }, []);

  return { projects, status, error, reload, optimisticUpdate, prepend };
}
