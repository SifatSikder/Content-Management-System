/* Sons Real Estate CMS — service worker.
 *
 * Two jobs:
 *   1. Installability — `display: standalone` from the manifest needs an
 *      active service worker for Chrome to fire `beforeinstallprompt`.
 *   2. Web Push — render OS notifications + route taps back into the app.
 *
 * We deliberately do NOT intercept fetch. Earlier this file ran a SWR
 * runtime cache for /projects/<uuid> which matched RSC + HTML requests to
 * the same cache entry and presented ERR_FAILED whenever the network step
 * threw. The cost (broken navigations after HMR) outweighed the benefit
 * (mild offline UX). If we want offline cache back later, key by mode +
 * Accept and gate behind feature-flag.
 *
 * Bump CACHE_VERSION on changes that need to evict prior storage.
 */

const CACHE_VERSION = "sre-v2";

self.addEventListener("install", () => {
  // Activate the new SW immediately; older clients pick up on next navigation.
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      // Evict every old cache from prior SW versions, including the v1 SWR cache.
      const keys = await caches.keys();
      await Promise.all(
        keys.filter((k) => !k.startsWith(CACHE_VERSION)).map((k) => caches.delete(k)),
      );
      await self.clients.claim();
    })(),
  );
});

// ---------- web push ----------

self.addEventListener("push", (event) => {
  if (!event.data) return;
  let payload;
  try {
    payload = event.data.json();
  } catch {
    payload = { title: "Sons RE CMS", body: event.data.text() };
  }
  const title = payload.title ?? "Sons RE CMS";
  const options = {
    body: payload.body ?? "",
    icon: "/icons/icon.svg",
    badge: "/icons/icon.svg",
    data: { url: payload.url ?? "/projects" },
    tag: payload.tag, // de-dupes when the same tag fires twice
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const targetUrl = event.notification.data?.url ?? "/projects";
  event.waitUntil(
    (async () => {
      const all = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      for (const client of all) {
        if (client.url.includes(self.location.origin)) {
          await client.focus();
          if ("navigate" in client) await client.navigate(targetUrl);
          return;
        }
      }
      await self.clients.openWindow(targetUrl);
    })(),
  );
});
