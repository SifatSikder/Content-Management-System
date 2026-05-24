"use client";

import { useCallback, useEffect, useState } from "react";

import { listMyBusinesses } from "@/features/businesses/api";
import type { MeBusinessEntry } from "@/features/businesses/types";

interface UseBusinessesState {
  status: "idle" | "loading" | "ready" | "error";
  items: MeBusinessEntry[];
  error: string | null;
  reload: () => Promise<void>;
}

export function useBusinesses(): UseBusinessesState {
  const [status, setStatus] = useState<UseBusinessesState["status"]>("loading");
  const [items, setItems] = useState<MeBusinessEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setStatus("loading");
    setError(null);
    try {
      const res = await listMyBusinesses();
      setItems(res.items);
      setStatus("ready");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Failed to load businesses");
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return { status, items, error, reload: load };
}
