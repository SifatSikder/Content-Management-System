import { type Role } from "@/features/auth/constants";

/** Public projection of a user — matches `app/schemas/auth.py` UserPublic. */
export interface AuthUser {
  id: string;
  email: string;
  name: string;
  role: Role;
  must_change_password: boolean;
  /** True iff this user is the CEO super-admin. Bypasses RLS + business membership checks. */
  is_super_admin: boolean;
  /** Cached Google profile picture URL, or null if the user has never used Google sign-in. */
  image: string | null;
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
