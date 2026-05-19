"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, getAccessToken, setAccessToken } from "@/lib/api-client";

import { fetchMe } from "../api";
import type { AuthUser } from "../types";

interface AuthState {
  status: "loading" | "authenticated" | "anonymous";
  user: AuthUser | null;
}

const _listeners = new Set<() => void>();

function notifyAuthChange() {
  _listeners.forEach((fn) => fn());
}

export function logout(): void {
  setAccessToken(null);
  notifyAuthChange();
}

export function loginWithToken(token: string): void {
  setAccessToken(token);
  notifyAuthChange();
}

export function useAuth(): AuthState & {
  refresh: () => Promise<void>;
  logout: () => void;
} {
  const [state, setState] = useState<AuthState>({ status: "loading", user: null });

  const refresh = useCallback(async () => {
    const token = getAccessToken();
    if (!token) {
      setState({ status: "anonymous", user: null });
      return;
    }
    try {
      const me = await fetchMe();
      setState({ status: "authenticated", user: me });
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setAccessToken(null);
      }
      setState({ status: "anonymous", user: null });
    }
  }, []);

  useEffect(() => {
    void refresh();
    const onChange = () => void refresh();
    _listeners.add(onChange);
    return () => {
      _listeners.delete(onChange);
    };
  }, [refresh]);

  return { ...state, refresh, logout };
}
