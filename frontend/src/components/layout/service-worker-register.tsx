"use client";

import { useEffect } from "react";

/**
 * Registers `/sw.js` on first paint.
 *
 * Idempotent — the browser dedupes against an existing registration. We
 * skip in dev only when `NEXT_PUBLIC_DISABLE_SW=1` is set (useful for
 * dashboard debugging where you don't want the runtime cache mediating
 * every request). The service worker itself is intentionally trivial; the
 * push event handler is the load-bearing piece.
 */
export function ServiceWorkerRegister(): null {
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!("serviceWorker" in navigator)) return;
    if (process.env.NEXT_PUBLIC_DISABLE_SW === "1") return;

    const register = async () => {
      try {
        await navigator.serviceWorker.register("/sw.js", { scope: "/" });
      } catch (err) {
        // Surface in dev console; production logs are out of scope here.
        console.warn("[sw] registration failed", err);
      }
    };
    // Defer slightly so it doesn't compete with the first paint critical path.
    if (document.readyState === "complete") {
      void register();
    } else {
      window.addEventListener("load", register, { once: true });
    }
  }, []);
  return null;
}
