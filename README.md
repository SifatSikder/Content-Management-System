# Sons Real Estate — Content Production CRM

Internal video-production pipeline tool for Sons Real Estate
([sonsrealestate.nl](https://sonsrealestate.nl)). Replaces a WhatsApp-only
workflow with a structured system that tracks every video from idea →
published, with emphasis on the editing-review phase.

## Stack

- **Backend** — FastAPI (Python 3.12) + async SQLAlchemy 2 + Alembic
- **Frontend** — Next.js 15 (App Router) + React 19 + TypeScript + Tailwind v4 + shadcn/ui
- **Database** — PostgreSQL 16
- **Cache / queue** — Redis 7 + `arq` (Phase 2+)
- **Storage** — Google Cloud Storage (a dev-only bucket with a 7-day lifecycle rule keeps cost negligible)
- **Hosting** — Hostinger VPS behind Caddy (Phase 5)

See `project_spec.md` for functional scope and `implementation_plan.md` for the
phase-by-phase task breakdown.

## Prerequisites

| Tool   | Version         | Install |
|--------|-----------------|---------|
| Python | 3.12+           | [python.org](https://www.python.org) or `pyenv` |
| `uv`   | latest          | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node   | 20+             | [nodejs.org](https://nodejs.org) |
| pnpm   | 11+             | `corepack enable && corepack prepare pnpm@latest --activate` |
| Docker | 24+             | [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/) |

## Quickstart

```bash
git clone <repo-url> sons-realestate-cms
cd sons-realestate-cms

# Copy env template (gitignored). Set at minimum: JWT_SECRET, CEO_EMAIL,
# CEO_NAME, CEO_INITIAL_PASSWORD.
cp .env.example .env.local

# Symlink so the Next.js app reads the same .env.local as the backend.
ln -sf "../.env.local" frontend/.env.local

# One-shot: install deps + start stack + apply migrations
make bootstrap

# Seed the CEO row (idempotent).
make seed

# In two separate terminals:
make dev       # FastAPI on http://localhost:8000
make dev-web   # Next.js on http://localhost:3000 (or :3001 if 3000 is busy)
```

- API health: <http://localhost:8000/healthz>
- Frontend: <http://localhost:3000>
- API docs (dev only): <http://localhost:8000/docs>

Sign in as the CEO with `CEO_EMAIL` + `CEO_INITIAL_PASSWORD`. The first login
redirects to `/change-password` to rotate the bootstrap password, then lands
on the kanban. Use `/team` (CEO-only) to invite the rest of the crew.

### Enabling real email (Gmail API)

Invitation + password-reset emails go through the Gmail API. Until you
configure it, the invite endpoint returns the accept-invite URL in the API
response so the admin can copy-paste it from the Team page.

In Google Cloud Console:

1. Enable the **Gmail API** (APIs & Services → Library).
2. Configure the **OAuth consent screen**: User type "External", add the
   sender mailbox (e.g. `sifatsikder2814@gmail.com`) as a Test User, include
   the scope `https://www.googleapis.com/auth/gmail.send`.
3. Create an **OAuth 2.0 Client ID of type "Web application"** (not Desktop —
   we use the production-shaped client type even though the sender is a
   personal account). Add `http://localhost:8765/oauth/gmail/callback` to
   "Authorized redirect URIs" (path + port must match exactly). Download
   `client_secret.json`.

Then run the helper once:

```bash
uv run python scripts/setup_gmail_oauth.py /path/to/client_secret.json
```

The script prints an auth URL → open in browser logged in as the sender
mailbox → approve → paste the full redirected URL back into the prompt →
get printed `GMAIL_OAUTH_*` values to put in `.env.local`.

> **Send-volume note**: a personal Gmail account caps daily transactional
> sends around 2,000 messages. Fine for the internal CMS use case; swap the
> backend to a dedicated ESP (Resend / SendGrid / SES) before this product
> ever talks to customers. The `server/email.ts` +
> `app/services/email_service.py` abstractions make that a contained change.

### Enabling Google sign-in (optional)

A **separate** OAuth client (type "Web application", scope `openid email
profile`, redirect URI `http://localhost:3001/api/auth/callback/google`).
Set `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, and
`NEXT_PUBLIC_GOOGLE_SIGN_IN_ENABLED=true` in `.env.local`. Google sign-in
only succeeds for emails already in `users` with `accepted_at IS NOT NULL`
(invite-only allowlist; matches the spec §6 "Manage users / roles: CEO only").

## Useful commands

```bash
make help                          # list all targets
make up / make down                # start / stop docker stack
make db-migration MSG="add foo"    # create an Alembic migration
make db-upgrade                    # apply migrations
make lint                          # ruff + codespell + no-raw-fetch + pnpm lint
make typecheck                     # mypy + tsc
```

## Project structure

```
.
├── alembic/             # SQLAlchemy migrations
├── app/                 # FastAPI backend
│   ├── main.py          # app factory + lifespan
│   ├── config.py        # pydantic-settings (single config singleton)
│   ├── models/          # ORM
│   ├── schemas/         # Pydantic DTOs
│   ├── routes/          # API routers (thin)
│   ├── services/        # business logic
│   ├── auth/            # jwt + dependencies (Phase 1)
│   └── jobs/            # arq workers (Phase 2+)
├── frontend/            # Next.js app
│   └── src/
│       ├── app/         # App Router
│       ├── components/
│       │   ├── ui/      # shadcn primitives
│       │   ├── layout/  # navbar, sidebar, theme toggle
│       │   ├── icons/
│       │   └── shared/
│       ├── features/    # feature-sliced modules (auth/, projects/, …)
│       └── lib/
│           └── api-client.ts   # SINGLE transport layer
├── infra/               # Caddyfile, systemd units, deploy scripts (Phase 5)
├── scripts/             # one-off CLI utilities
├── docker-compose.yml   # local Postgres + Redis
├── pyproject.toml       # uv-managed Python deps
└── Makefile             # canonical entrypoint
```

## Auth flow

The browser-facing auth surface is **NextAuth v5** (Auth.js). FastAPI no
longer mints tokens; it only validates the cookie JWT (same `JWT_SECRET`,
HS256) as a bearer when needed.

- `frontend/src/auth.ts` — Credentials provider (email + bcrypt) + Google OAuth.
- `frontend/src/server/{db,users,tokens,password,email}.ts` — narrow direct
  Postgres access for `users` and `one_time_tokens`. All other writes still
  go through FastAPI.
- `app/auth/` is now just a JWT decoder for `/auth/me`.

The CEO row is seeded from `CEO_EMAIL` / `CEO_NAME` / `CEO_INITIAL_PASSWORD`.
Team members are added via the `/team` page; invitations live in the
`one_time_tokens` table with a 7-day TTL.

## Conventions

- **One config singleton** — `app/config.py` is the only place env vars are read.
- **One HTTP transport** — `frontend/src/lib/api-client.ts` is the only file
  allowed to call `fetch()` (with `features/edits/lib/resumable-upload.ts`
  allow-listed for GCS chunked uploads). The lint target enforces this.
- **Layering** — Routes → Services → Models. Services do not import FastAPI;
  models do not import routes or services.
- **Migrations** — every new model is imported in `alembic/env.py`.
- **Feature slices** — new frontend code lives under `frontend/src/features/<name>/`.
- **`.env.local` symlink** — `frontend/.env.local → ../.env.local` so the
  backend and Next.js share env vars (`JWT_SECRET`, Gmail creds, etc.).
