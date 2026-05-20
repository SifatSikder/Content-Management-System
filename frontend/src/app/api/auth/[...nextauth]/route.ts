/**
 * NextAuth catch-all route handler — exposes /api/auth/signin,
 * /api/auth/signout, /api/auth/callback/credentials, /api/auth/session, etc.
 *
 * All real auth logic lives in `frontend/src/auth.ts`.
 */

import { handlers } from "@/auth";

export const { GET, POST } = handlers;
