/**
 * Web Push subscribe/unsubscribe helpers.
 *
 * `pushSupported()` returns false in environments without ServiceWorker,
 * PushManager, or Notification — e.g. private browsing on iOS < 16.4,
 * SSR, in-app webviews. Callers should guard UI on this before showing
 * subscribe controls.
 *
 * The flow:
 *   1. Wait for the service worker registration (registered in
 *      ServiceWorkerRegister on app boot).
 *   2. Ask the user for `Notification.requestPermission()`.
 *   3. Subscribe with the VAPID public key (base64url → Uint8Array).
 *   4. POST the resulting endpoint + keys to /push/subscribe.
 */

import { getVapidPublicKey, subscribePush, unsubscribePush } from "@/features/push/api";

export function pushSupported(): boolean {
  if (typeof window === "undefined") return false;
  return (
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window
  );
}

function urlBase64ToUint8Array(b64: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (b64.length % 4)) % 4);
  const normalized = (b64 + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(normalized);
  const buf = new ArrayBuffer(raw.length);
  const out = new Uint8Array(buf);
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

function arrayBufferToBase64Url(buf: ArrayBuffer | null): string {
  if (!buf) return "";
  const bytes = new Uint8Array(buf);
  let bin = "";
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

async function getRegistration(): Promise<ServiceWorkerRegistration> {
  const existing = await navigator.serviceWorker.getRegistration();
  if (existing) return existing;
  // Browser hasn't installed the SW yet (first paint race). Wait once.
  return await navigator.serviceWorker.ready;
}

export async function enablePush(): Promise<PushSubscription> {
  if (!pushSupported()) throw new Error("Push not supported in this browser");

  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    throw new Error(
      permission === "denied"
        ? "Notifications blocked — re-enable them in your browser settings."
        : "Permission not granted",
    );
  }

  const { public_key } = await getVapidPublicKey();
  const registration = await getRegistration();
  const existing = await registration.pushManager.getSubscription();
  // Re-subscribe if the existing subscription used a different VAPID key.
  if (existing) await existing.unsubscribe();

  const sub = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(public_key),
  });

  await subscribePush({
    endpoint: sub.endpoint,
    p256dh_key: arrayBufferToBase64Url(sub.getKey("p256dh")),
    auth_key: arrayBufferToBase64Url(sub.getKey("auth")),
    user_agent: navigator.userAgent,
  });
  return sub;
}

export async function disablePush(): Promise<void> {
  if (!pushSupported()) return;
  const registration = await navigator.serviceWorker.getRegistration();
  if (!registration) return;
  const sub = await registration.pushManager.getSubscription();
  if (!sub) return;
  try {
    await unsubscribePush({
      endpoint: sub.endpoint,
      p256dh_key: arrayBufferToBase64Url(sub.getKey("p256dh")),
      auth_key: arrayBufferToBase64Url(sub.getKey("auth")),
    });
  } catch {
    // Best-effort — even if the backend call fails, drop the browser subscription.
  }
  await sub.unsubscribe();
}

export async function getCurrentSubscription(): Promise<PushSubscription | null> {
  if (!pushSupported()) return null;
  const registration = await navigator.serviceWorker.getRegistration();
  if (!registration) return null;
  return await registration.pushManager.getSubscription();
}
