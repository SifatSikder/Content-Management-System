/**
 * One-time tokens (invitations + password resets) — Next.js side.
 *
 * The raw token is sent in the email link. We persist only its SHA-256 hex
 * digest; consume = look up by hash, verify expiry + unconsumed, mark
 * consumed_at, return the user_id.
 *
 * Backed by the same `one_time_tokens` table the FastAPI side defines via
 * `app/models/one_time_token.py` (purpose: 'invitation' | 'password_reset').
 */

import { randomBytes, createHash } from "node:crypto";

import { getPool } from "./db";

export type TokenPurpose = "invitation" | "password_reset";

export class TokenNotFoundError extends Error {
  constructor() {
    super("token not found");
    this.name = "TokenNotFoundError";
  }
}
export class TokenExpiredError extends Error {
  constructor() {
    super("token expired");
    this.name = "TokenExpiredError";
  }
}
export class TokenAlreadyUsedError extends Error {
  constructor() {
    super("token already used");
    this.name = "TokenAlreadyUsedError";
  }
}

function sha256Hex(raw: string): string {
  return createHash("sha256").update(raw, "utf8").digest("hex");
}

function urlSafeToken(bytes = 32): string {
  return randomBytes(bytes).toString("base64url");
}

/**
 * Mint a fresh token for the user/purpose and return the raw value to embed
 * in the email URL. Any prior unconsumed token of the same purpose for the
 * same user is deleted in the same transaction — so "resend invite" / "I
 * forgot again" never leaves stale tokens lying around.
 */
export async function mintToken(opts: {
  userId: string;
  purpose: TokenPurpose;
  ttlSeconds: number;
}): Promise<string> {
  const raw = urlSafeToken();
  const hash = sha256Hex(raw);
  const expiresAt = new Date(Date.now() + opts.ttlSeconds * 1000);

  const pool = getPool();
  const client = await pool.connect();
  try {
    await client.query("BEGIN");
    await client.query(
      `DELETE FROM one_time_tokens
       WHERE user_id = $1 AND purpose = $2 AND consumed_at IS NULL`,
      [opts.userId, opts.purpose],
    );
    await client.query(
      `INSERT INTO one_time_tokens (id, user_id, token_hash, purpose, expires_at)
       VALUES (gen_random_uuid(), $1, $2, $3, $4)`,
      [opts.userId, hash, opts.purpose, expiresAt],
    );
    await client.query("COMMIT");
    return raw;
  } catch (err) {
    await client.query("ROLLBACK");
    throw err;
  } finally {
    client.release();
  }
}

/**
 * Consume a token. On success, marks it `consumed_at = now()` and returns
 * the owning user_id. Throws specific subclasses for each rejection reason.
 */
export async function consumeToken(opts: {
  raw: string;
  purpose: TokenPurpose;
}): Promise<{ userId: string }> {
  const hash = sha256Hex(opts.raw);
  const pool = getPool();
  const client = await pool.connect();
  try {
    await client.query("BEGIN");
    const found = await client.query<{
      id: string;
      user_id: string;
      expires_at: Date;
      consumed_at: Date | null;
    }>(
      `SELECT id, user_id, expires_at, consumed_at
       FROM one_time_tokens
       WHERE token_hash = $1 AND purpose = $2
       FOR UPDATE`,
      [hash, opts.purpose],
    );
    if (found.rowCount === 0) {
      await client.query("ROLLBACK");
      throw new TokenNotFoundError();
    }
    const row = found.rows[0];
    if (row.consumed_at !== null) {
      await client.query("ROLLBACK");
      throw new TokenAlreadyUsedError();
    }
    if (new Date(row.expires_at).getTime() < Date.now()) {
      await client.query("ROLLBACK");
      throw new TokenExpiredError();
    }
    await client.query(`UPDATE one_time_tokens SET consumed_at = now() WHERE id = $1`, [row.id]);
    await client.query("COMMIT");
    return { userId: row.user_id };
  } catch (err) {
    if (
      !(err instanceof TokenNotFoundError) &&
      !(err instanceof TokenAlreadyUsedError) &&
      !(err instanceof TokenExpiredError)
    ) {
      try {
        await client.query("ROLLBACK");
      } catch {
        /* ignore */
      }
    }
    throw err;
  } finally {
    client.release();
  }
}
