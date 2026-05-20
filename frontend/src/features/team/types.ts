import type { Role } from "@/lib/enums";

export interface TeamMember {
  id: string;
  email: string;
  name: string;
  role: Role;
  created_at: string;
  invited_at: string | null;
  accepted_at: string | null;
  last_login_at: string | null;
  status: "active" | "pending" | "unknown";
}

export interface TeamListResponse {
  items: TeamMember[];
}

export interface InvitePayload {
  email: string;
  name: string;
  role: Role;
}

export interface InviteResponse {
  user_id: string;
  invite_url_for_admin?: string;
}
