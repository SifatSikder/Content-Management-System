/**
 * The SINGLE HTTP client for the whole frontend.
 *
 * Per the project blueprint, NO other file may call `fetch` directly.
 * Features import `apiFetch` (unauthenticated) or `apiFetchAuthed` (reads JWT
 * from sessionStorage and injects `Authorization: Bearer …`) from here.
 *
 * Responsibilities:
 *   - Resolve the base URL from `NEXT_PUBLIC_API_URL`.
 *   - Inject `Content-Type: application/json` for JSON bodies; pass FormData
 *     through unchanged.
 *   - Deserialize typed JSON responses; handle 204 / empty bodies safely.
 *   - Throw a typed `ApiError(status, message, detail)` on non-2xx, parsing
 *     FastAPI's `{ detail: … }` body when present.
 *
 * It knows nothing about React, routing, feature state, or business logic.
 * All cross-cutting transport concerns (retry, tracing, refresh) belong here.
 */

const DEFAULT_BASE_URL = "http://localhost:8000";
const TOKEN_STORAGE_KEY = "sre.access_token";

/** Thrown for any non-2xx response. */
export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(status: number, message: string, detail: unknown = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

function resolveBaseUrl(): string {
  const fromEnv = process.env.NEXT_PUBLIC_API_URL;
  return (fromEnv && fromEnv.trim()) || DEFAULT_BASE_URL;
}

function isFormData(body: unknown): body is FormData {
  return typeof FormData !== "undefined" && body instanceof FormData;
}

function shouldSerializeJson(body: BodyInit | null | undefined): boolean {
  if (body === null || body === undefined) return false;
  if (typeof body === "string") return false;
  if (isFormData(body)) return false;
  if (body instanceof Blob) return false;
  if (body instanceof URLSearchParams) return false;
  if (body instanceof ArrayBuffer) return false;
  return true;
}

async function parseError(response: Response): Promise<ApiError> {
  let detail: unknown = null;
  let message = `Request failed with status ${response.status}`;
  try {
    const text = await response.text();
    if (text) {
      try {
        const parsed = JSON.parse(text);
        detail = parsed?.detail ?? parsed;
        if (typeof detail === "string") {
          message = detail;
        } else if (
          parsed &&
          typeof parsed === "object" &&
          "detail" in parsed &&
          typeof (parsed as { detail: unknown }).detail === "string"
        ) {
          message = (parsed as { detail: string }).detail;
        }
      } catch {
        detail = text;
        message = text;
      }
    }
  } catch {
    // swallow body-read failures; the status is still informative
  }
  return new ApiError(response.status, message, detail);
}

async function parseSuccess<T>(response: Response): Promise<T> {
  if (response.status === 204) {
    return undefined as T;
  }
  const text = await response.text();
  if (!text) {
    return undefined as T;
  }
  return JSON.parse(text) as T;
}

/** Read the JWT from sessionStorage. SSR-safe — returns null on the server. */
export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.sessionStorage.getItem(TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

/** Persist the JWT to sessionStorage. SSR-safe — no-op on the server. */
export function setAccessToken(token: string | null): void {
  if (typeof window === "undefined") return;
  try {
    if (token) {
      window.sessionStorage.setItem(TOKEN_STORAGE_KEY, token);
    } else {
      window.sessionStorage.removeItem(TOKEN_STORAGE_KEY);
    }
  } catch {
    // best-effort
  }
}

async function request<T>(
  path: string,
  init: RequestInit | undefined,
  token: string | null,
): Promise<T> {
  const url = path.startsWith("http")
    ? path
    : `${resolveBaseUrl()}${path.startsWith("/") ? path : `/${path}`}`;

  const headers = new Headers(init?.headers);
  let body = init?.body;

  if (shouldSerializeJson(body)) {
    body = JSON.stringify(body);
    if (!headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
  }

  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }

  const response = await fetch(url, { ...init, body, headers });

  if (!response.ok) {
    throw await parseError(response);
  }

  return parseSuccess<T>(response);
}

/** Unauthenticated request — no Authorization header is added. */
export function apiFetch<T = unknown>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  return request<T>(path, init, null);
}

/** Authenticated request — JWT read from sessionStorage and sent as Bearer. */
export function apiFetchAuthed<T = unknown>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  return request<T>(path, init, getAccessToken());
}
