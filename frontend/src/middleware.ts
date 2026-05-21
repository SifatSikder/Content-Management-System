/**
 * Edge auth guard.
 *
 * Runs on every matched request and decides where the user is allowed to be
 * before the page renders. The Route Handlers under /api/auth/* enforce the
 * same checks server-side; this middleware is defense-in-depth + UX (no flash
 * of authed content for anonymous users).
 *
 *   anon                                  → /
 *   authed on /                           → /projects (or /change-password)
 *   authed with must_change_password=true → pinned to /change-password
 *
 * Public paths: `/`, `/accept-invite`, `/reset-password`, `/api/auth/*`.
 *
 * NextAuth's v5 `auth()` middleware can't be used here because our root
 * `@/auth` pulls in Credentials.authorize() — which imports `pg` + `bcryptjs`,
 * neither of which run in the Edge runtime. We decode the JWS HS256 cookie
 * manually with `jose` (edge-safe) using the same JWT_SECRET as the backend.
 */

import { type NextRequest, NextResponse } from "next/server";
import { jwtVerify } from "jose";

const PUBLIC_PATHS = ["/", "/accept-invite", "/reset-password"];
const CHANGE_PASSWORD_PATH = "/change-password";
const DEFAULT_AUTHED_DESTINATION = "/projects";

function isPublicPath(pathname: string): boolean {
  if (PUBLIC_PATHS.includes(pathname)) return true;
  if (pathname.startsWith("/api/auth/")) return true;
  return false;
}

function secretKey(): Uint8Array | null {
  const raw =
    process.env.JWT_SECRET ?? process.env.AUTH_SECRET ?? process.env.NEXTAUTH_SECRET;
  if (!raw) return null;
  return new TextEncoder().encode(raw);
}

interface SessionClaims {
  sub: string;
  must_change_password: boolean;
}

async function readSession(req: NextRequest): Promise<SessionClaims | null> {
  const cookieName =
    process.env.NODE_ENV === "production"
      ? "__Secure-authjs.session-token"
      : "authjs.session-token";
  const token = req.cookies.get(cookieName)?.value;
  if (!token) return null;
  const key = secretKey();
  if (!key) return null;
  try {
    const { payload } = await jwtVerify(token, key);
    const sub = typeof payload.sub === "string" ? payload.sub : null;
    if (!sub) return null;
    return {
      sub,
      must_change_password: Boolean(
        (payload as Record<string, unknown>).must_change_password,
      ),
    };
  } catch {
    return null;
  }
}

export async function middleware(req: NextRequest): Promise<NextResponse> {
  const { pathname } = req.nextUrl;

  // Never gate /api/auth/* — NextAuth needs unimpeded access to its own
  // route handlers regardless of auth state. Redirecting these (e.g. when
  // must_change_password=true) would force JSON-expecting clients to parse
  // the change-password page HTML and throw ClientFetchError.
  if (pathname.startsWith("/api/auth/")) return NextResponse.next();

  const session = await readSession(req);

  if (!session) {
    if (isPublicPath(pathname)) return NextResponse.next();
    const url = req.nextUrl.clone();
    url.pathname = "/";
    url.search = "";
    return NextResponse.redirect(url);
  }

  // Authenticated below.
  if (session.must_change_password && pathname !== CHANGE_PASSWORD_PATH) {
    const url = req.nextUrl.clone();
    url.pathname = CHANGE_PASSWORD_PATH;
    url.search = "";
    return NextResponse.redirect(url);
  }

  if (pathname === "/") {
    const url = req.nextUrl.clone();
    url.pathname = session.must_change_password
      ? CHANGE_PASSWORD_PATH
      : DEFAULT_AUTHED_DESTINATION;
    url.search = "";
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

// Skip Next internals and static assets so the matcher doesn't run on every
// _next/static request. We let /api/auth pass to the matcher and rely on
// `isPublicPath` to short-circuit there.
export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\..*).*)"],
};
