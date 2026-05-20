/**
 * User-table operations the Next.js layer owns.
 *
 * Keep this surface narrow: the FastAPI side is the canonical writer for
 * everything else. We touch `users` here only for:
 *   - reading by email/id during sign-in
 *   - last_login_at bookkeeping
 *   - creating an invited row
 *   - flipping password_hash + must_change_password on accept/change/reset
 *   - soft-delete on remove
 *
 * Returned types deliberately mirror the FastAPI schema names so the rest of
 * the frontend can reuse the existing `Role` enum.
 */

import type { Role } from "@/lib/enums";

import { getPool, withTransaction } from "./db";

export interface ActiveUser {
  id: string;
  email: string;
  name: string;
  role: Role;
  locale: string;
  password_hash: string | null;
  must_change_password: boolean;
  invited_at: Date | null;
  accepted_at: Date | null;
  avatar_url: string | null;
}

export interface UserAdminView extends ActiveUser {
  created_at: Date;
  last_login_at: Date | null;
}

async function rowToActive(row: Record<string, unknown> | undefined): Promise<ActiveUser | null> {
  if (!row) return null;
  return {
    id: row.id as string,
    email: row.email as string,
    name: row.name as string,
    role: row.role as Role,
    locale: row.locale as string,
    password_hash: (row.password_hash as string | null) ?? null,
    must_change_password: row.must_change_password as boolean,
    invited_at: (row.invited_at as Date | null) ?? null,
    accepted_at: (row.accepted_at as Date | null) ?? null,
    avatar_url: (row.avatar_url as string | null) ?? null,
  };
}

export async function getActiveUserByEmail(email: string): Promise<ActiveUser | null> {
  const result = await getPool().query(
    `SELECT id, email, name, role, locale, password_hash, must_change_password,
            invited_at, accepted_at, avatar_url
       FROM users
      WHERE lower(email) = lower($1) AND deleted_at IS NULL
      LIMIT 1`,
    [email],
  );
  return rowToActive(result.rows[0]);
}

export async function getActiveUserById(id: string): Promise<ActiveUser | null> {
  const result = await getPool().query(
    `SELECT id, email, name, role, locale, password_hash, must_change_password,
            invited_at, accepted_at, avatar_url
       FROM users
      WHERE id = $1 AND deleted_at IS NULL
      LIMIT 1`,
    [id],
  );
  return rowToActive(result.rows[0]);
}

export async function touchLastLogin(id: string): Promise<void> {
  await getPool().query(`UPDATE users SET last_login_at = now() WHERE id = $1`, [id]);
}

/** Update avatar_url. Called from the Google sign-in callback. */
export async function setAvatarUrl(id: string, url: string | null): Promise<void> {
  await getPool().query(`UPDATE users SET avatar_url = $1 WHERE id = $2`, [url, id]);
}

/** Create a pending user (no password, no accepted_at). Returns the new id. */
export async function createInvitedUser(opts: {
  email: string;
  name: string;
  role: Role;
  invitedBy: string;
}): Promise<string> {
  const result = await getPool().query<{ id: string }>(
    `INSERT INTO users (id, email, name, role, locale, invited_at, invited_by)
     VALUES (gen_random_uuid(), $1, $2, $3, 'nl', now(), $4)
     RETURNING id`,
    [opts.email.toLowerCase(), opts.name, opts.role, opts.invitedBy],
  );
  return result.rows[0].id;
}

/** Mark an invited user accepted: set password hash, accepted_at, clear must_change. */
export async function acceptInvitedUser(opts: {
  userId: string;
  passwordHash: string;
  name?: string;
}): Promise<void> {
  await getPool().query(
    `UPDATE users
        SET password_hash = $1,
            accepted_at = COALESCE(accepted_at, now()),
            must_change_password = false,
            name = COALESCE($2, name)
      WHERE id = $3`,
    [opts.passwordHash, opts.name ?? null, opts.userId],
  );
}

/** Update password hash + clear must_change_password (used by change + reset flows). */
export async function setPassword(opts: { userId: string; passwordHash: string }): Promise<void> {
  await getPool().query(
    `UPDATE users
        SET password_hash = $1,
            must_change_password = false
      WHERE id = $2`,
    [opts.passwordHash, opts.userId],
  );
}

/** Soft-delete a user (CEO "Remove" action). Tokens cascade-delete via FK. */
export async function softDeleteUser(id: string): Promise<void> {
  await getPool().query(`UPDATE users SET deleted_at = now() WHERE id = $1`, [id]);
}

export async function listAllUsers(): Promise<UserAdminView[]> {
  const result = await getPool().query(
    `SELECT id, email, name, role, locale, password_hash, must_change_password,
            invited_at, accepted_at, avatar_url, created_at, last_login_at
       FROM users
      WHERE deleted_at IS NULL
      ORDER BY created_at DESC`,
  );
  return result.rows.map((row) => ({
    id: row.id,
    email: row.email,
    name: row.name,
    role: row.role,
    locale: row.locale,
    password_hash: row.password_hash,
    must_change_password: row.must_change_password,
    invited_at: row.invited_at,
    accepted_at: row.accepted_at,
    avatar_url: row.avatar_url ?? null,
    created_at: row.created_at,
    last_login_at: row.last_login_at,
  }));
}

/**
 * Idempotent "create or revive": if a user exists with this email, returns its id.
 * Used by the invite flow so a CEO can re-invite a previously-removed teammate.
 */
export async function findOrCreateInvitedUser(opts: {
  email: string;
  name: string;
  role: Role;
  invitedBy: string;
}): Promise<{ id: string; alreadyAccepted: boolean }> {
  return withTransaction(async (client) => {
    const found = await client.query<{
      id: string;
      accepted_at: Date | null;
      deleted_at: Date | null;
    }>(
      `SELECT id, accepted_at, deleted_at FROM users WHERE lower(email) = lower($1)`,
      [opts.email],
    );
    if (found.rowCount && found.rowCount > 0) {
      const row = found.rows[0];
      // Revive on re-invite: clear deleted_at, refresh invited_at, update name/role.
      await client.query(
        `UPDATE users
            SET deleted_at = NULL,
                invited_at = now(),
                invited_by = $1,
                name = $2,
                role = $3
          WHERE id = $4`,
        [opts.invitedBy, opts.name, opts.role, row.id],
      );
      return { id: row.id, alreadyAccepted: row.accepted_at !== null };
    }
    const created = await client.query<{ id: string }>(
      `INSERT INTO users (id, email, name, role, locale, invited_at, invited_by)
       VALUES (gen_random_uuid(), $1, $2, $3, 'nl', now(), $4)
       RETURNING id`,
      [opts.email.toLowerCase(), opts.name, opts.role, opts.invitedBy],
    );
    return { id: created.rows[0].id, alreadyAccepted: false };
  });
}
