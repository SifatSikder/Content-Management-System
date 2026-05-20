import type { Role } from "@/lib/enums";

/** Public projection of a user — matches `app/schemas/auth.py` UserPublic. */
export interface AuthUser {
  id: string;
  email: string;
  name: string;
  role: Role;
  must_change_password: boolean;
}

export interface AcceptInviteBody {
  token: string;
  password: string;
  name?: string;
}

export interface RequestResetBody {
  email: string;
}

export interface ResetPasswordBody {
  token: string;
  password: string;
}

export interface ChangePasswordBody {
  current_password: string;
  new_password: string;
}
