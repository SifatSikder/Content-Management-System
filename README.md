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
- **Storage** — Google Cloud Storage (Phase 1+); `fake-gcs-server` in dev
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

# Copy env template (gitignored — fill in dev secrets if any)
cp .env.example .env.local

# One-shot: install deps + start stack + apply migrations
make bootstrap

# In two separate terminals:
make dev       # FastAPI on http://localhost:8000
make dev-web   # Next.js on http://localhost:3000
```

- API health check: <http://localhost:8000/healthz>
- Frontend: <http://localhost:3000>
- API docs (dev only): <http://localhost:8000/docs>

## Useful commands

```bash
make help                          # list all targets
make up / make down                # start / stop docker stack
make db-migration MSG="add foo"    # create an Alembic migration
make db-upgrade                    # apply migrations
make lint                          # ruff + codespell + no-raw-fetch + pnpm lint
make typecheck                     # mypy + tsc
make test                          # pytest (Phase 1+ adds frontend tests)
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
├── docker-compose.yml   # local Postgres + Redis + fake-gcs-server
├── pyproject.toml       # uv-managed Python deps
└── Makefile             # canonical entrypoint
```

## Conventions

- **One config singleton** — `app/config.py` is the only place env vars are read.
- **One HTTP transport** — `frontend/src/lib/api-client.ts` is the only file
  allowed to call `fetch()`. The lint target enforces this.
- **Layering** — Routes → Services → Models. Services do not import FastAPI;
  models do not import routes or services.
- **Migrations** — every new model is imported in `alembic/env.py`.
- **Feature slices** — new frontend code lives under `frontend/src/features/<name>/`.
