/**
 * Postgres connection pool — used by the Next.js server modules for the
 * narrow set of mutations they own (users + one_time_tokens).
 *
 * Every other write (projects, scripts, edits) still goes through FastAPI;
 * the Next.js layer touches the DB directly only for auth-table operations
 * where it would be silly to round-trip through the backend.
 */

import { Pool, type PoolClient } from "pg";

// Mirrors backend DATABASE_URL_SYNC but with the pg-native scheme.
// .env.local supplies DATABASE_URL_SYNC=postgresql+psycopg2://… — we strip
// the `+psycopg2` suffix for node-pg.
function buildConnectionString(): string {
  const raw = process.env.DATABASE_URL_SYNC ?? process.env.DATABASE_URL;
  if (!raw) {
    throw new Error(
      "DATABASE_URL_SYNC (or DATABASE_URL) must be set for the Next.js server modules.",
    );
  }
  return raw.replace("postgresql+psycopg2://", "postgresql://").replace(
    "postgresql+asyncpg://",
    "postgresql://",
  );
}

// HMR-safe singleton: Next.js dev mode tears down + rebuilds module instances
// on every save, so we cache on globalThis.
declare global {
  var __pgPool: Pool | undefined;
}

export function getPool(): Pool {
  if (!globalThis.__pgPool) {
    globalThis.__pgPool = new Pool({
      connectionString: buildConnectionString(),
      max: 10,
      idleTimeoutMillis: 30_000,
    });
  }
  return globalThis.__pgPool;
}

/** Run a function inside a transaction. Rolls back on throw. */
export async function withTransaction<T>(
  fn: (client: PoolClient) => Promise<T>,
): Promise<T> {
  const client = await getPool().connect();
  try {
    await client.query("BEGIN");
    const result = await fn(client);
    await client.query("COMMIT");
    return result;
  } catch (err) {
    await client.query("ROLLBACK");
    throw err;
  } finally {
    client.release();
  }
}
