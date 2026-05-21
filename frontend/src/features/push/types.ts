export interface VapidPublicKeyResponse {
  public_key: string;
}

export interface SubscribePushBody {
  endpoint: string;
  p256dh_key: string;
  auth_key: string;
  user_agent?: string | null;
}

export interface PushSubscriptionPublic {
  id: string;
  user_id: string;
  endpoint: string;
  user_agent: string | null;
  created_at: string;
  last_used_at: string | null;
}
