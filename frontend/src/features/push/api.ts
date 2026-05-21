import { apiFetchAuthed } from "@/lib/api-client";

import type {
  PushSubscriptionPublic,
  SubscribePushBody,
  VapidPublicKeyResponse,
} from "./types";

export function getVapidPublicKey(): Promise<VapidPublicKeyResponse> {
  return apiFetchAuthed<VapidPublicKeyResponse>(`/push/vapid-public-key`);
}

export function subscribePush(body: SubscribePushBody): Promise<PushSubscriptionPublic> {
  return apiFetchAuthed<PushSubscriptionPublic>(`/push/subscribe`, {
    method: "POST",
    body: body as unknown as BodyInit,
  });
}

export function unsubscribePush(body: SubscribePushBody): Promise<void> {
  return apiFetchAuthed<void>(`/push/unsubscribe`, {
    method: "POST",
    body: body as unknown as BodyInit,
  });
}
