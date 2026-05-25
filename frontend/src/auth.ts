/**
 * NextAuth (Auth.js v5) — single source of truth for browser-facing auth.
 *
 * The session cookie IS a JWS HS256 token signed with the same JWT_SECRET as
 * the FastAPI backend. That means the cookie is *also* a valid bearer token
 * for backend endpoints — no separate token exchange needed.
 *
 * Providers:
 *   - Credentials  : email + password (bcrypt hash in the users table)
 *   - Google OAuth : added in a follow-up; "Sign in with Google" only succeeds
 *                    for emails already in users with accepted_at IS NOT NULL
 *                    (invite-only allowlist).
 *
 * The custom `jwt.encode` / `jwt.decode` overrides force JWS HS256 instead of
 * NextAuth's default JWE so the FastAPI decoder in `app/auth/jwt.py` accepts
 * the cookie as a bearer.
 */

import { cookies } from "next/headers";
import NextAuth, { type DefaultSession, type NextAuthConfig } from "next-auth";
import type { Provider } from "next-auth/providers";
import Credentials from "next-auth/providers/credentials";
import Google from "next-auth/providers/google";
import { SignJWT, jwtVerify } from "jose";

import { type Role } from "@/features/auth/constants";
import { verifyPassword } from "@/server/password";
import { getActiveUserByEmail, setAvatarUrl, touchLastLogin } from "@/server/users";

// 1 hour — matches Settings.jwt_ttl_seconds on the backend.
const JWT_TTL_SECONDS = 3600;

// Constant-time decoy: bcrypt hash of a random string nobody knows. Used by
// `authorize()` when the email isn't on file so the bcrypt cost is paid
// either way — closes the email-enumeration timing oracle.
const DUMMY_PASSWORD_HASH =
  "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW";

// Augment NextAuth types so callers see role + must_change_password +
// is_super_admin + accessToken.
declare module "next-auth" {
  interface Session {
    accessToken?: string;
    user: {
      id: string;
      role: Role;
      must_change_password: boolean;
      is_super_admin: boolean;
    } & DefaultSession["user"];
  }
  interface User {
    role?: Role;
    must_change_password?: boolean;
  }
}

// NB: we don't augment the JWT type — see commentary on `jwt()` callback.
// NextAuth v5's JWT type lives in @auth/core/jwt; the module name varies
// between versions and the augmentation is fragile, so we keep the custom
// claims off-types and access them with `as` casts in two well-defined spots
// (jwt callback, session callback). Token shape on the wire stays exact.

/**
 * Build the provider list at boot. Credentials is always on. Google is added
 * only if both GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET are set,
 * so a developer without Google OAuth credentials still gets a working app.
 */
function buildProviders(): Provider[] {
  const providers: Provider[] = [
    Credentials({
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        const email = typeof credentials?.email === "string" ? credentials.email : null;
        const password =
          typeof credentials?.password === "string" ? credentials.password : null;
        if (!email || !password) return null;

        const user = await getActiveUserByEmail(email);
        // Always run bcrypt so the response time doesn't reveal whether the
        // email exists. DUMMY_HASH is a fixed $2b$ hash that will never match
        // any real password — the compare runs purely to burn the same CPU.
        const hashToCheck = user?.password_hash ?? DUMMY_PASSWORD_HASH;
        const ok = await verifyPassword(password, hashToCheck);
        if (!user || !user.password_hash || !user.accepted_at || !ok) return null;

        await touchLastLogin(user.id);
        return {
          id: user.id,
          email: user.email,
          name: user.name,
          image: user.avatar_url,
          role: user.role,
          must_change_password: user.must_change_password,
        };
      },
    }),
  ];

  const googleId = process.env.GOOGLE_OAUTH_CLIENT_ID;
  const googleSecret = process.env.GOOGLE_OAUTH_CLIENT_SECRET;
  if (googleId && googleSecret) {
    providers.push(
      Google({
        clientId: googleId,
        clientSecret: googleSecret,
        // Bind to the standard OIDC scopes — anything more (e.g. gmail.send)
        // is the responsibility of the separate Gmail-send OAuth client.
        authorization: { params: { scope: "openid email profile" } },
      }),
    );
  }
  return providers;
}

/** True when Google sign-in is enabled. Read by the login UI. */
export const googleSignInEnabled = (): boolean =>
  Boolean(process.env.GOOGLE_OAUTH_CLIENT_ID && process.env.GOOGLE_OAUTH_CLIENT_SECRET);

function secretKey(secret: string | string[]): Uint8Array {
  const raw = typeof secret === "string" ? secret : secret[0];
  if (!raw) {
    throw new Error("JWT_SECRET (or AUTH_SECRET) must be set.");
  }
  return new TextEncoder().encode(raw);
}

function authSecret(): string {
  const s = process.env.JWT_SECRET ?? process.env.AUTH_SECRET ?? process.env.NEXTAUTH_SECRET;
  if (!s) {
    throw new Error("JWT_SECRET must be set (shared with the FastAPI backend).");
  }
  return s;
}

const config: NextAuthConfig = {
  session: { strategy: "jwt", maxAge: JWT_TTL_SECONDS },
  secret: authSecret(),
  trustHost: true,
  pages: { signIn: "/", error: "/" },
  providers: buildProviders(),
  // Override NextAuth's default JWE encoding with plain JWS HS256 so the
  // cookie payload is the same shape FastAPI expects (sub/email/role/iat/exp).
  jwt: {
    async encode({ token, secret, maxAge }) {
      const issuedAt = Math.floor(Date.now() / 1000);
      const expiresAt = issuedAt + (maxAge ?? JWT_TTL_SECONDS);
      const t = (token ?? {}) as Record<string, unknown>;
      const payload: Record<string, unknown> = {
        sub: t.sub,
        email: t.email,
        name: t.name,
        picture: t.picture,
        role: t.role,
        must_change_password: t.must_change_password,
        is_super_admin: t.is_super_admin,
      };
      return await new SignJWT(payload)
        .setProtectedHeader({ alg: "HS256", typ: "JWT" })
        .setIssuedAt(issuedAt)
        .setExpirationTime(expiresAt)
        .sign(secretKey(secret));
    },
    async decode({ token, secret }) {
      if (!token) return null;
      try {
        const { payload } = await jwtVerify(token, secretKey(secret));
        return payload as Record<string, unknown>;
      } catch {
        return null;
      }
    },
  },
  callbacks: {
    // Google sign-in allowlist: only emails that already exist in `users` and
    // have accepted_at IS NOT NULL are allowed in. Prevents random Google
    // accounts from self-signing-up — matches the CEO-controlled invite model.
    async signIn({ user, account, profile }) {
      if (account?.provider !== "google") return true;
      if (!user.email) return false;
      const known = await getActiveUserByEmail(user.email);
      if (!known?.accepted_at) return false;
      // Hand the role + must_change_password back to the jwt callback by
      // assigning to the `user` parameter. NextAuth threads it through.
      (user as { role?: Role; must_change_password?: boolean }).role = known.role;
      (user as { role?: Role; must_change_password?: boolean }).must_change_password =
        known.must_change_password;
      (user as { id?: string }).id = known.id;
      // Cache Google's picture so credentials-only sessions get the same avatar.
      const picture =
        (profile as { picture?: string } | null | undefined)?.picture ?? user.image ?? null;
      if (picture && picture !== known.avatar_url) {
        await setAvatarUrl(known.id, picture);
      }
      (user as { image?: string | null }).image = picture ?? known.avatar_url ?? null;
      await touchLastLogin(known.id);
      return true;
    },
    async jwt({ token, user }) {
      // Initial sign-in: pull custom claims off the User returned by authorize().
      if (user) {
        token.sub = user.id;
        token.email = user.email ?? undefined;
        token.name = user.name ?? undefined;
        token.picture = user.image ?? undefined;
        (token as Record<string, unknown>).role = user.role;
        (token as Record<string, unknown>).must_change_password =
          user.must_change_password ?? false;
        // CEO super-admin is the only platform-wide bypass for RLS + business
        // membership checks. Mirrors `UserModel.is_super_admin` on the backend.
        (token as Record<string, unknown>).is_super_admin = user.role === "ceo";
      }
      return token;
    },
    async session({ session, token }) {
      const t = token as Record<string, unknown>;
      session.user.id = token.sub!;
      session.user.role = (t.role as Role) ?? "viewer";
      session.user.must_change_password = Boolean(t.must_change_password);
      session.user.is_super_admin = Boolean(t.is_super_admin);
      session.user.name = (t.name as string | undefined) ?? session.user.name ?? null;
      session.user.image = (t.picture as string | undefined) ?? session.user.image ?? null;

      // Expose the cookie's JWS to client code so apiFetchAuthed can send it
      // as `Authorization: Bearer …` against FastAPI.
      const cookieStore = await cookies();
      const cookieName =
        process.env.NODE_ENV === "production"
          ? "__Secure-authjs.session-token"
          : "authjs.session-token";
      const sessionToken = cookieStore.get(cookieName)?.value;
      if (sessionToken) {
        session.accessToken = sessionToken;
      }
      return session;
    },
  },
};

export const { handlers, auth, signIn, signOut } = NextAuth(config);
