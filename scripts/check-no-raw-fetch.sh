#!/usr/bin/env bash
# Blueprint guard: NO file under frontend/src/ may call `fetch(` directly.
# The only legal home for transport is `frontend/src/lib/api-client.ts`.
# Features import `apiFetch` / `apiFetchAuthed` from there.
#
# Run via `make lint`. Fails CI on the first offender.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$REPO_ROOT/frontend/src"

if [ ! -d "$SRC" ]; then
  echo "skip: $SRC not present yet"
  exit 0
fi

# grep returns 1 when no matches found — we negate that so "no matches" = success.
# Allowlist (in addition to api-client.ts):
#   - resumable-upload.ts talks to GCS session URLs directly (not our backend),
#     so it intentionally uses raw fetch with custom Content-Range headers.
MATCHES=$(grep -rn --include='*.ts' --include='*.tsx' \
            --exclude='api-client.ts' \
            --exclude='resumable-upload.ts' \
            -E '\bfetch\s*\(' \
            "$SRC" || true)

if [ -n "$MATCHES" ]; then
  echo "✘ Raw fetch() found outside frontend/src/lib/api-client.ts:"
  echo ""
  echo "$MATCHES"
  echo ""
  echo "Use apiFetch / apiFetchAuthed from @/lib/api-client instead."
  exit 1
fi

echo "✓ no raw fetch() outside api-client.ts"
