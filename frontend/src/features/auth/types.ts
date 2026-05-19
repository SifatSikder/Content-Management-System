import type { Role } from "@/lib/enums";

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  role: Role;
  locale: string;
}

export interface VerifyResponse {
  access_token: string;
  user: AuthUser;
}

export interface RequestLinkBody {
  email: string;
  locale?: string;
}
