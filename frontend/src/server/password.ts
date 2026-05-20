/**
 * bcrypt password hashing — `bcryptjs` produces the same `$2b$` OpenBSD
 * format as Python's `bcrypt` module on the backend, so hashes round-trip
 * cleanly between the two runtimes.
 *
 * OpenBSD bcrypt caps password input at 72 bytes. We enforce that explicitly
 * so a 73-byte password isn't silently truncated.
 */

import bcrypt from "bcryptjs";

const SALT_ROUNDS = 12;
export const MIN_PASSWORD_LENGTH = 8;
export const MAX_PASSWORD_BYTES = 72;

export class PasswordTooShortError extends Error {
  constructor() {
    super(`Password must be at least ${MIN_PASSWORD_LENGTH} characters.`);
    this.name = "PasswordTooShortError";
  }
}

export class PasswordTooLongError extends Error {
  constructor() {
    super(`Password must be at most ${MAX_PASSWORD_BYTES} UTF-8 bytes (bcrypt cap).`);
    this.name = "PasswordTooLongError";
  }
}

function assertValid(plain: string): void {
  if (plain.length < MIN_PASSWORD_LENGTH) throw new PasswordTooShortError();
  if (new TextEncoder().encode(plain).byteLength > MAX_PASSWORD_BYTES) {
    throw new PasswordTooLongError();
  }
}

export async function hashPassword(plain: string): Promise<string> {
  assertValid(plain);
  return bcrypt.hash(plain, SALT_ROUNDS);
}

export async function verifyPassword(plain: string, hash: string): Promise<boolean> {
  if (!plain || !hash) return false;
  try {
    return await bcrypt.compare(plain, hash);
  } catch {
    return false;
  }
}
