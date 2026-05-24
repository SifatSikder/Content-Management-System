"use client";

import { useCallback, useEffect, useState } from "react";

import { listDepartments, listMyDepartments } from "@/features/departments/api";
import type { Department, MeDepartmentEntry } from "@/features/departments/types";

interface DeptListState {
  status: "idle" | "loading" | "ready" | "error";
  items: Department[];
  error: string | null;
  reload: () => Promise<void>;
}

export function useDepartments(businessId: string | null): DeptListState {
  const [status, setStatus] = useState<DeptListState["status"]>("idle");
  const [items, setItems] = useState<Department[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!businessId) {
      setItems([]);
      setStatus("ready");
      return;
    }
    setStatus("loading");
    setError(null);
    try {
      const res = await listDepartments(businessId);
      setItems(res.items);
      setStatus("ready");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Failed to load departments");
      setStatus("error");
    }
  }, [businessId]);

  useEffect(() => {
    void load();
  }, [load]);

  return { status, items, error, reload: load };
}

interface MyDeptState {
  status: "idle" | "loading" | "ready" | "error";
  items: MeDepartmentEntry[];
  error: string | null;
  reload: () => Promise<void>;
}

export function useMyDepartments(businessId: string | null): MyDeptState {
  const [status, setStatus] = useState<MyDeptState["status"]>("idle");
  const [items, setItems] = useState<MeDepartmentEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!businessId) {
      setItems([]);
      setStatus("ready");
      return;
    }
    setStatus("loading");
    setError(null);
    try {
      const res = await listMyDepartments(businessId);
      setItems(res.items);
      setStatus("ready");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Failed to load departments");
      setStatus("error");
    }
  }, [businessId]);

  useEffect(() => {
    void load();
  }, [load]);

  return { status, items, error, reload: load };
}
