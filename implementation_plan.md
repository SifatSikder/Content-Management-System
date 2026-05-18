# Sons Real Estate — Content Production CRM
## Technical Implementation Plan

Developer-facing plan derived from `project_spec.md` and the user's project blueprint. Organised phase → task → subtask. Hour estimates assume a solo developer comfortable with Python/FastAPI + TypeScript/React/Postgres + basic Linux sysadmin. Pad by 30% for unknowns.

**Stack**: Next.js 15 (React 19 + TS + Tailwind v4 + shadcn/ui) ↔ FastAPI (Python 3.12, async SQLAlchemy 2.x) ↔ PostgreSQL 16 ↔ Redis 7 ↔ **Google Cloud Storage** (`europe-west4`, NL). All compute (eventually) deployed on **Hostinger VPS** behind **Caddy**. Python backend chosen for Phase 5+ AI/transcoding/ML readiness (Vertex AI optional).

**Blueprint adherence**: `uv` package manager · Makefile entrypoint · `app/{models,schemas,routes,services,auth,jobs}` layout · feature-sliced frontend · all HTTP via `frontend/src/lib/api-client.ts`.

**Build philosophy**: Phases 0–4 happen entirely on the developer's laptop against a local `docker-compose` stack with mocked external services. **Deployment is not a phase concern until Phase 5.** Sign up for production accounts only when going live.

---

## Repo Layout

```
sons-realestate-cms/
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app + lifespan
│   ├── config.py               # pydantic-settings, async + sync DB URLs, dev-mode flag
│   ├── models/                 # SQLAlchemy ORM (UserModel, ProjectModel, …)
│   ├── schemas/                # Pydantic DTOs
│   ├── routes/                 # health, auth, projects, scripts, edits, locations, …
│   ├── services/               # business logic (no FastAPI imports)
│   ├── auth/
│   │   ├── jwt.py
│   │   └── dependencies.py     # current_user, require_role, require_project_access
│   └── jobs/                   # arq worker functions (push, whatsapp, transcoding)
│       ├── __init__.py
│       └── worker.py
├── frontend/
│   ├── package.json
│   ├── next.config.ts
│   ├── tsconfig.json
│   ├── postcss.config.mjs      # Tailwind v4 via @tailwindcss/postcss
│   └── src/
│       ├── app/
│       │   ├── layout.tsx
│       │   ├── page.tsx        # / (login entry)
│       │   ├── globals.css     # shadcn CSS vars (light + .dark)
│       │   └── (authenticated)/
│       │       ├── layout.tsx
│       │       ├── projects/{page.tsx, [id]/page.tsx}
│       │       ├── dashboard/page.tsx
│       │       └── settings/page.tsx
│       ├── components/
│       │   ├── ui/             # shadcn primitives (auto-generated)
│       │   ├── layout/         # DashboardNavbar, Sidebar, MobileBottomNav, ThemeToggle
│       │   ├── icons/          # lucide-react re-exports
│       │   └── shared/         # ConfirmDialog, EmptyState, ErrorState
│       ├── features/
│       │   ├── auth/
│       │   ├── projects/
│       │   ├── scripts/
│       │   ├── edits/
│       │   ├── locations/
│       │   ├── casting/
│       │   ├── shoots/
│       │   └── dashboard/
│       └── lib/
│           └── api-client.ts   # SINGLE transport — apiFetch + apiFetchAuthed
├── infra/                      # (skeleton created in Phase 0; fleshed out in Phase 5)
│   ├── Caddyfile
│   ├── systemd/
│   └── scripts/
├── scripts/
│   ├── create_admin.py
│   └── seed_demo.py
├── alembic.ini
├── pyproject.toml              # uv-managed
├── uv.lock
├── Makefile
├── docker-compose.yml          # local Postgres + Redis + fake-gcs-server
├── .env.example
└── README.md
```

**Conventions**
- ✅ = blocking acceptance criterion
- ⏱ = rough hours (single dev, focused)
- 🔗 = dependency on a prior task
- 🐍 backend ▪ ⚛️ frontend ▪ 🛠 infra (Phase 5 only)

---

# Phase 0 — Codebase Scaffolding (local-only)  ⏱ 10–12h, ≈1–2 days

**Goal**: a developer can clone the repo, run `make install && make dev` and have a working empty FastAPI app + empty Next.js app + Postgres + Redis + a local GCS-compatible storage emulator + Alembic ready to migrate. **No VPS, no external accounts, no production secrets.**

### Task 0.1 — Init repo + Python toolchain  ⏱ 2h 🐍
- 0.1.1 `git init`; baseline `.gitignore` (Python, Node, env, build artifacts).
- 0.1.2 `pyproject.toml` via `uv init`. Add deps: `fastapi`, `uvicorn[standard]`, `sqlalchemy[asyncio]`, `alembic`, `pydantic-settings`, `asyncpg`, `psycopg2-binary` (Alembic sync driver), `python-jose[cryptography]`, `passlib[bcrypt]`, `google-cloud-storage`, `httpx`, `structlog`, `slowapi`, `arq`, `redis`, `email-validator`.
- 0.1.3 Dev deps: `ruff`, `mypy`, `codespell`, `pytest`, `pytest-asyncio`, `pytest-cov`, `httpx` (test client).
- 0.1.4 `ruff` + `mypy` + `codespell` config blocks in `pyproject.toml` (blueprint defaults).
- 0.1.5 `uv sync` once to populate `uv.lock`; commit.

### Task 0.2 — FastAPI skeleton + lifespan + config  ⏱ 3h 🐍
- 0.2.1 `app/__init__.py`.
- 0.2.2 `app/config.py`: `Settings(BaseSettings)` with `database_url` (async), `database_url_sync` (Alembic), `redis_url`, `jwt_secret`, `jwt_ttl_seconds`, `magic_link_ttl_seconds`, `storage_emulator_host` (dev-only), `gcs_bucket_video`, `gcs_bucket_backups`, `app_env` (`dev`/`prod`), `cors_origins`. `@lru_cache get_settings()` singleton. Computed: `is_dev`, `is_prod`.
- 0.2.3 `app/main.py`: app factory, lifespan that warms DB pool + Redis ping + fail-fast settings validation. CORS middleware from settings.
- 0.2.4 `app/routes/health.py`: `/healthz` pings DB + Redis; `/readyz` lighter.
- 0.2.5 `structlog` config (JSON in prod, pretty in dev), global exception handlers (HTTPException, RequestValidationError, fallback 500 with request_id).
- 0.2.6 Hit `uvicorn app.main:app --reload` → `curl localhost:8000/healthz` returns 200.

### Task 0.3 — Alembic + base model  ⏱ 2h 🐍
- 0.3.1 `alembic init alembic` (async template).
- 0.3.2 `alembic/env.py`: imports `app.config.get_settings`, uses `database_url_sync`; imports every model under `app.models` with `# noqa: F401` (placeholder — real models land in Phase 1).
- 0.3.3 `app/models/base.py`: `Base = declarative_base()`, async engine factory, async session factory, `TimestampMixin` (created_at/updated_at server defaults), `UUIDPrimaryKeyMixin`.
- 0.3.4 `alembic.ini` points at `alembic/` and reads URL from `app.config`.
- 0.3.5 `make db-migration MSG="bootstrap"` produces an empty migration; `make db-upgrade` succeeds against the docker-compose Postgres.

### Task 0.4 — Next.js + shadcn + transport layer  ⏱ 4h ⚛️
- 0.4.1 `pnpm create next-app@latest frontend --typescript --tailwind --app --src-dir --turbopack --import-alias "@/*"`.
- 0.4.2 In `frontend/`: `pnpm add next-intl next-themes framer-motion lucide-react clsx tailwind-merge zod react-hook-form @hookform/resolvers @dnd-kit/core @dnd-kit/sortable @tiptap/react @tiptap/starter-kit @tiptap/extension-link`.
- 0.4.3 Tailwind v4: replace generated `globals.css` with `@import "tailwindcss";` + shadcn CSS variable block (`:root` + `.dark`, oklch tokens).
- 0.4.4 `npx shadcn@latest init` (New York style, Slate base, CSS variables, RSC=yes, `@/components`, `@/lib/utils`).
- 0.4.5 `npx shadcn@latest add button input label form textarea dialog alert-dialog sheet drawer dropdown-menu popover tooltip hover-card card badge avatar separator skeleton scroll-area tabs select combobox command toast sonner progress slider checkbox switch radio-group table calendar`
- 0.4.6 `frontend/src/lib/api-client.ts` **created before any feature code** — `apiFetch<T>`, `apiFetchAuthed<T>`, `ApiError(status, message, detail)`, SSR-safe `sessionStorage` reads, FormData passthrough, JSON content-type injection, 204/empty handling.
- 0.4.7 CI guard script `scripts/check-no-raw-fetch.sh` (used in Makefile `lint`): `grep -r "fetch(" frontend/src --exclude-dir=node_modules --exclude=lib/api-client.ts` → fail if any hit.
- 0.4.8 `next-intl` config + `messages/nl.json` + `messages/en.json` with three placeholder strings each.
- 0.4.9 `next-themes` provider in root `layout.tsx`; `ThemeToggle` stub in `components/layout/`.
- 0.4.10 Sonner `<Toaster />` mounted in root layout.
- 0.4.11 `pnpm dev` → `http://localhost:3000` renders an empty page in Dutch with theme toggle working.

### Task 0.5 — docker-compose local stack  ⏱ 2h 🐍/⚛️
- 0.5.1 `docker-compose.yml` with:
   - `postgres:16-alpine` (named volume, `cms` DB, `cms_app` user).
   - `redis:7-alpine` (named volume, `requirepass`).
   - `fsouza/fake-gcs-server` (port 4443, scheme http, public-host `localhost:4443`) — local GCS emulator.
- 0.5.2 `.env.example`: all settings keys with safe local defaults. `STORAGE_EMULATOR_HOST=http://localhost:4443`, `APP_ENV=dev`, `JWT_SECRET=changeme-local-dev-only`, etc.
- 0.5.3 `make up` brings the stack up; `make down` stops it.
- 0.5.4 First-run helper: `make bootstrap` runs `uv sync`, `pnpm --filter frontend install`, `make up`, `make db-upgrade`.

### Task 0.6 — Makefile + dev mocks for email/WhatsApp  ⏱ 1.5h 🐍
- 0.6.1 `Makefile` targets:
   ```
   make help          # auto-generated from ## comments
   make bootstrap     # one-shot: install + up + migrate
   make install       # uv sync + pnpm install
   make up / down     # docker-compose
   make dev           # uvicorn --reload
   make dev-web       # pnpm --filter frontend dev
   make dev-worker    # arq app.jobs.worker.WorkerSettings (Phase 2+; stub now)
   make db-migration MSG="..."
   make db-upgrade
   make db-downgrade
   make lint          # ruff + mypy + codespell + scripts/check-no-raw-fetch.sh + pnpm lint
   make typecheck     # mypy app + pnpm --filter frontend type-check
   make test          # pytest + pnpm --filter frontend test
   make seed          # uv run python scripts/seed_demo.py
   ```
- 0.6.2 `app/services/email_service.py` (stub): in dev mode writes `.dev-emails/<timestamp>.html` to disk AND prints magic-link URL to console; in prod calls Resend (Phase 5).
- 0.6.3 `app/services/whatsapp_service.py` (stub): in dev mode logs `[whatsapp:dev] would send: …`; in prod calls Meta API (Phase 5 wiring of real credentials, but the call site exists from Phase 3).

### Task 0.7 — README quickstart + GitHub Actions (test/lint only)  ⏱ 1.5h 🛠
- 0.7.1 README: project overview, prerequisites (Docker, uv, pnpm, Python 3.12, Node 20), `make bootstrap` quickstart, `make help` reference, link to `project_spec.md`.
- 0.7.2 `.github/workflows/ci.yml`: on PR/push to main, run `make lint && make typecheck && make test` against a service-container Postgres + Redis. **No deploy step yet** — that's Phase 5.
- 0.7.3 Push initial commit to a private GitHub repo.

✅ **Phase 0 done when**:
- `git clone … && make bootstrap` works on a clean machine.
- `make dev` and `make dev-web` start both apps; `/healthz` returns 200; `/` renders an empty Next.js page.
- Alembic migrations run cleanly against docker-compose Postgres.
- CI passes on first push.
- **Zero production secrets exist anywhere in the repo or developer's machine.**

---

# Phase 1 — MVP  (8–11 weeks, ≈220–265h)

Build the whole MVP locally against the docker-compose stack. Mocked email (writes to disk) and mocked WhatsApp (logs). Real `fake-gcs-server` for upload/download flows. No VPS work happens here.

Split into **Backend** and **Frontend** tracks.

---

## Backend Track 🐍 (~110h)

### Task 1.1 — Structured logging + global error handling polish  ⏱ 4h  🔗 0.2
- 1.1.1 Verify `structlog` JSON-vs-pretty switch on `APP_ENV`.
- 1.1.2 Request-ID middleware (`X-Request-ID` in/out, included in every log).
- 1.1.3 OpenAPI tags per router; CI step exports `openapi.json` artifact for the frontend TS-type generator.

### Task 1.2 — Models + Alembic schema  ⏱ 16h  🔗 0.3
- 1.2.1 Models (one file each): `user.py`, `project.py`, `script.py` (`ScriptModel`, `ScriptVersionModel`, `ScriptCommentModel`), `edit.py` (`EditVersionModel`, `EditCommentModel`), `activity.py`, `notification.py`. Skeleton: `location.py`, `cast_member.py`, `shoot.py`.
- 1.2.2 Postgres enums for `role`, `category`, `pipeline_stage`, `edit_status`.
- 1.2.3 Indexes: `(project_id, created_at)` on activity/comments; FTS placeholder.
- 1.2.4 Every model imported in `alembic/env.py` with `# noqa: F401`.
- 1.2.5 `make db-migration MSG="initial schema"`; review and commit.
- 1.2.6 `scripts/seed_demo.py`: idempotent — 1 CEO + 1 director + 1 editor + 1 crew + 2 demo projects.

### Task 1.3 — Auth: magic-link + JWT (sessionStorage flow)  ⏱ 18h  🔗 1.1
- 1.3.1 `app/auth/jwt.py`: encode/decode + helpers.
- 1.3.2 `app/services/auth_service.py`: request-link (mint token, persist, call email_service), verify (consume, issue JWT).
- 1.3.3 `app/routes/auth.py`:
   - `POST /auth/request-link` (200 even on unknown email — anti-enumeration).
   - `GET /auth/verify?token=…` → `{access_token, user}`; frontend stores in `sessionStorage`.
   - `GET /auth/me`.
- 1.3.4 `slowapi` rate limit: 5/min per IP on `/auth/request-link`.
- 1.3.5 Magic-link HTML template (Dutch + English) via `email_service` (dev: writes to `.dev-emails/`; print magic-link URL to console for fast testing).
- 1.3.6 Token TTLs: magic-link 15 min, JWT 1h.
- 1.3.7 Tests: happy path, expired token, reused token, unknown email, locale switching.

### Task 1.4 — `app/auth/dependencies.py` permissions layer  ⏱ 12h  🔗 1.3
- 1.4.1 `current_user` dependency.
- 1.4.2 `require_role(*roles)` factory.
- 1.4.3 `require_project_access(level)`.
- 1.4.4 `can_user_move_to_stage(user, project, target_stage)` (spec §6 matrix).
- 1.4.5 Permission denials logged structured.
- 1.4.6 Tests: each role × representative endpoint.

### Task 1.5 — Project CRUD endpoints  ⏱ 14h  🔗 1.4
- 1.5.1 `app/routes/projects.py` + `app/services/project_service.py`.
- 1.5.2 `POST /projects`, `GET /projects?stage=…&owner=…&filter=mine`, `GET /projects/{id}`.
- 1.5.3 `PATCH /projects/{id}`.
- 1.5.4 `POST /projects/{id}/stage` — guarded by `can_user_move_to_stage`.
- 1.5.5 Activity written via `activity_service.log(...)` on every mutation.
- 1.5.6 Soft-delete + restore.
- 1.5.7 Cursor pagination.

### Task 1.6 — Script + versions + comments  ⏱ 14h  🔗 1.5
- 1.6.1 `app/routes/scripts.py` + service.
- 1.6.2 `POST /projects/{id}/scripts/versions` (markdown body).
- 1.6.3 `GET …/versions`, `GET …/versions/{vid}`.
- 1.6.4 `POST /scripts/versions/{vid}/comments` + resolve/reopen.
- 1.6.5 `POST /projects/{id}/scripts/submit` → advances stage.
- 1.6.6 `POST /projects/{id}/scripts/lock` (director+), `/unlock` (CEO/Asst Dir).
- 1.6.7 Activity entries on each.

### Task 1.7 — Edit upload + GCS signed URLs (against fake-gcs-server)  ⏱ 16h  🔗 1.5
- 1.7.1 `app/services/storage_service.py` wrapping `google-cloud-storage` (via `asyncio.to_thread`). Reads `STORAGE_EMULATOR_HOST` env in dev to route to `fake-gcs-server`; in prod uses the real GCS endpoint.
- 1.7.2 `POST /projects/{id}/edits/init-upload` → `Blob.create_resumable_upload_session(content_type, size)` → returns session URL.
- 1.7.3 Client PUTs chunks to the session URL with `Content-Range`. Max 2 GB.
- 1.7.4 `POST /projects/{id}/edits` — finalise: verify blob, create `EditVersionModel`, status `in_review`.
- 1.7.5 `GET /edits/{id}/playback-url` — V4 signed read URL, 15 min TTL.
- 1.7.6 Content-type allow-list (`video/mp4`, `video/quicktime`).
- 1.7.7 `POST /edits/{id}/approve` and `/request-changes` (role-gated).
- 1.7.8 V2-upload payload includes resolved-comments map.

> **Why resumable uploads instead of S3-style multipart**: GCS's native protocol. One signed session URL handles chunking, retries, and resume. The same code works against `fake-gcs-server` in dev and real GCS in prod.

### Task 1.8 — Edit comments + activity feed endpoints  ⏱ 10h  🔗 1.7
- 1.8.1 `POST /edits/{id}/comments` with `timestamp_seconds`.
- 1.8.2 `GET /edits/{id}/comments`.
- 1.8.3 Resolve / reopen.
- 1.8.4 `GET /projects/{id}/activity` paginated.

### Task 1.9 — Email service stub formalised  ⏱ 6h
- 1.9.1 Magic-link template (NL + EN), polished HTML.
- 1.9.2 Email service: dev mode writes `.dev-emails/*.html` AND prints URL to console; prod adapter exists but is a no-op until Phase 5 swaps in Resend SDK.

---

## Frontend Track ⚛️ (~115h)

### Task 1.11 — Foundation: design system + `api-client.ts` + auth UI  ⏱ 28h  🔗 1.3 endpoints

**1.11.A — Design system bootstrap  ⏱ 8h**
- 1.11.A.1 Verify Phase-0 shadcn setup (tokens, dark mode, primitives installed).
- 1.11.A.2 Pick a base palette aligned with sonsrealestate.nl branding (neutral grayscale + one accent, oklch values).
- 1.11.A.3 `cn()` util in `lib/utils.ts` (clsx + tailwind-merge).
- 1.11.A.4 Dev-only `/design` page rendering one of each primitive (in-house storybook).
- 1.11.A.5 Document theme & motion conventions in `frontend/README.md`.

**1.11.B — Transport layer hardening  ⏱ 4h**
- 1.11.B.1 Confirm `api-client.ts` + CI guard from Phase 0 are working; add unit tests for `ApiError` parsing, 204 handling, FormData passthrough.

**1.11.C — Auth slice  ⏱ 10h**
- 1.11.C.1 `features/auth/api.ts` thin wrappers (request-link, verify, me) via `apiFetch` / `apiFetchAuthed`.
- 1.11.C.2 `features/auth/hooks/useAuth.ts` — `sessionStorage` token + `/auth/me`.
- 1.11.C.3 `/` page: email Input + Button + shadcn `Form` + react-hook-form + zod → request-link → "check your inbox" Card.
- 1.11.C.4 `/auth/callback?token=…` handles verify, stashes JWT in `sessionStorage`, redirects.
- 1.11.C.5 `(authenticated)/layout.tsx` guard: no token / 401 → redirect to `/`.

**1.11.D — App shell  ⏱ 6h**
- 1.11.D.1 Desktop Sidebar (collapsible) + Sheet on mobile.
- 1.11.D.2 Mobile BottomNav with framer-motion `layoutId` active indicator.
- 1.11.D.3 Top bar: Avatar + DropdownMenu (profile, logout, theme).
- 1.11.D.4 ThemeToggle (Sun/Moon icons).

### Task 1.12 — `features/projects/` + Kanban  ⏱ 26h  🔗 1.5, 1.11
- 1.12.1 `types.ts` mirrors `app/schemas/project.py`.
- 1.12.2 `api.ts` typed wrappers via `apiFetchAuthed`.
- 1.12.3 `hooks/useProjects.ts` — fetch + manual invalidation on mutation.
- 1.12.4 `components/KanbanBoard.tsx` — 12 columns, `@dnd-kit/core` desktop drag.
- 1.12.5 `components/ProjectCard.tsx` — title, category icon, owner avatar, due pill, sub-state badge.
- 1.12.6 Drag handler: optimistic local move → API → revert + toast on error.
- 1.12.7 Mobile column swiper (CSS scroll-snap), card menu "Move to stage".
- 1.12.8 `CreateProjectDialog`.
- 1.12.9 `FilterBar`.
- 1.12.10 Empty / loading / error states.

### Task 1.13 — Project detail shell  ⏱ 12h  🔗 1.12
- 1.13.1 `/(authenticated)/projects/[id]/page.tsx` server-rendered header.
- 1.13.2 Tabs: Brief, Script, Location, Casting, Shoot, Edits, Activity.
- 1.13.3 Mobile horizontal pill bar.
- 1.13.4 `BriefTab.tsx` (read + inline edit).
- 1.13.5 `ActivityTab.tsx`.

### Task 1.14 — `features/scripts/` editor  ⏱ 24h  🔗 1.6, 1.13
- 1.14.1 Tiptap editor with markdown roundtrip.
- 1.14.2 `api.ts` typed wrappers.
- 1.14.3 Version list (Sheet) + diff view between two versions.
- 1.14.4 Inline paragraph comments with threading + resolve.
- 1.14.5 Submit / Lock / Unlock buttons (role-gated client, enforced server).
- 1.14.6 Autosave drafts to local storage as a safety net.

### Task 1.15 — `features/edits/` upload + review player  ⏱ 30h  🔗 1.7, 1.13
- 1.15.1 `api.ts` — init-upload, finalise, list versions, comments CRUD, approve / request-changes.
- 1.15.2 Upload component: file picker → `init-upload` → resumable PUT in 8 MB chunks with `Content-Range`, handles 308 + retries → finalise.
- 1.15.3 Progress UI (shadcn `Progress`), pause/resume, cancel (DELETE session).
- 1.15.4 Custom HTML5 video player.
- 1.15.5 Timeline click → Popover comment with timestamp prefilled.
- 1.15.6 Comment list synced (click jumps player).
- 1.15.7 Request changes (required note, AlertDialog) and Approve cut (AlertDialog).
- 1.15.8 V2 upload: checklist of unresolved V1 comments → POSTed in finalise.

### Task 1.16 — Activity log UI + polish  ⏱ 6h  🔗 1.8
- 1.16.1 Activity feed with localised verbs.
- 1.16.2 Sonner toasts on action results.

---

## Design System — shadcn primitive → feature map

| Feature / surface | Primitives used |
|---|---|
| **Auth** | Form, Input, Label, Button, Card, Skeleton, Sonner toast |
| **App shell** | Sheet, DropdownMenu, Avatar, Separator, ThemeToggle, Tabs |
| **Kanban** | Card, Badge, Avatar, ScrollArea, Tooltip, DropdownMenu, Skeleton, Dialog, Combobox, Calendar |
| **Project detail** | Tabs, Card, Badge, Separator, Button, AlertDialog |
| **Script editor** | Sheet, Tiptap + Button, Tooltip, AlertDialog, Sonner |
| **Edit review player** | Progress, Slider (custom timeline), Popover, Sheet, AlertDialog, HoverCard |
| **Location** (Phase 2) | Form, Input, Combobox, Card, Switch |
| **Casting** (Phase 2) | Table, Form, Input, Switch, AlertDialog, Avatar |
| **Shoot** (Phase 2) | Card, Calendar, Checkbox, Badge, Button |
| **Dashboard** (Phase 3) | Card, Badge, Tabs, HoverCard, Skeleton |
| **Settings** (Phase 3) | Form, Input, Select, Switch, RadioGroup, Button, Separator, AlertDialog |
| **Global search** (Phase 4) | Command, Dialog, Badge, Avatar |
| **PDF export status** (Phase 4) | Progress, Card, Sonner |

**Theme & motion conventions**: oklch CSS variables only (no hard-coded hex); Tailwind spacing scale only; framer-motion for Sidebar/Sheet/Drawer slides, kanban card lift, tab fade-in; respect `prefers-reduced-motion`; rely on shadcn's ARIA + focus for primitives, add focus rings + keyboard handlers on custom (kanban card, video player).

---

## ✅ Phase 1 acceptance (local dev environment)
- User logs in via magic-link (URL read from `.dev-emails/` or console), JWT stashed in `sessionStorage`, lands on Dutch UI.
- CEO creates a project, drags through stages.
- Director writes script V1 → submits → comments → V2 → locks.
- Editor uploads 1.5 GB MP4 cut V1 against `fake-gcs-server`; reviewer scrubs, comments at 0:34, requests changes.
- Editor uploads V2 with V1 comments checked off.
- Reviewer approves cut.
- Permission test: `crew` user cannot create projects or approve cuts.
- `lint`, `typecheck`, `test` all green in CI.
- `grep -r "fetch(" frontend/src` (minus `lib/api-client.ts`) returns zero hits.

---

# Phase 2 — Field Features + PWA + Push  (3–4 weeks, ≈70–90h)

Still local. Sign up for Google Maps Platform when starting this phase (free tier ample for dev). VAPID keys generated locally.

## Backend
### Task 2.1 — Location / Casting / Shoot endpoints  ⏱ 16h  🔗 1.5
- 2.1.1 Routes + services per blueprint (`app/routes/locations.py`, `casting.py`, `shoots.py`).
- 2.1.2 Photo upload via GCS resumable session URLs.
- 2.1.3 Shoot state machine (`scheduled` → `in_progress` → `wrapped`).

### Task 2.2 — `app/jobs/` arq worker  ⏱ 10h  🔗 0.5
- 2.2.1 `app/jobs/worker.py` exports `WorkerSettings`.
- 2.2.2 Add `arq` service to docker-compose? No — run `make dev-worker` as a separate local process.
- 2.2.3 Helpers in `app/services/queue_service.py`.

### Task 2.3 — Web Push delivery  ⏱ 10h  🔗 2.2
- 2.3.1 Generate dev VAPID keypair (committed to `.env.example` template, NOT to .env).
- 2.3.2 `POST /push/subscribe` persists subscription.
- 2.3.3 `app/jobs/push.py` sends via `pywebpush` (works locally — push goes to the browser's push service over HTTPS, browser handles delivery; localhost subscriptions work).
- 2.3.4 Per-user notification prefs endpoints.

## Frontend
### Task 2.4 — Feature slices: locations / casting / shoots  ⏱ 20h  🔗 2.1
- 2.4.1 `features/locations/` — Google Maps Platform Places Autocomplete + Maps JS API map preview + camera photo upload + confirmed Switch. `NEXT_PUBLIC_GOOGLE_MAPS_KEY` HTTP-referrer-restricted.
- 2.4.2 `features/casting/` — list + release form upload + confirmed.
- 2.4.3 `features/shoots/` — schedule + call sheet + gear checklist + status.
- 2.4.4 Pinned "Today's shoot" card on mobile home for `crew`.

### Task 2.5 — PWA + push  ⏱ 14h
- 2.5.1 `next-pwa`, manifest, icons (192/512/maskable).
- 2.5.2 Service worker with SWR cache for project detail (24h).
- 2.5.3 Install prompt component.
- 2.5.4 Push subscription flow + prefs UI.

## ✅ Phase 2 acceptance (local)
- Crew member opens today's shoot card on a phone pointed at the dev laptop's IP, marks "in progress" offline.
- New cut upload triggers a web push to a logged-in browser within 30s.

---

# Phase 3 — WhatsApp Bridge + Dashboards + Google Drive  (2–3 weeks, ≈50–65h)

Still local. WhatsApp stays mocked (calls go to console). Drive needs a real OAuth client — use a personal Google account for dev.

## Backend
### Task 3.1 — WhatsApp Cloud API integration (dev-mocked)  ⏱ 16h
- 3.1.1 `app/services/whatsapp_service.py` real Meta API client path — but `is_dev` short-circuits to console log.
- 3.1.2 `app/jobs/whatsapp.py` worker job.
- 3.1.3 Dedup + rate-limit so a burst sends a digest.
- 3.1.4 Admin settings UI for group ID + token (Phase 5 fills in real values).

### Task 3.2 — Dashboard endpoints  ⏱ 8h
- 3.2.1 `GET /dashboard/awaiting`.
- 3.2.2 `GET /dashboard/stages`.
- 3.2.3 `GET /dashboard/stuck?days=5`.
- 3.2.4 `GET /dashboard/throughput`.
- 3.2.5 `GET /dashboard/time-in-stage`.

### Task 3.3 — Google Drive  ⏱ 12h
- 3.3.1 Per-user OAuth (`google-auth-oauthlib`) — tokens encrypted at rest.
- 3.3.2 `POST /projects/{id}/drive/attach`.
- 3.3.3 `POST /projects/{id}/scripts/import-gdoc` → HTML → markdown.

## Frontend
### Task 3.4 — `features/dashboard/`  ⏱ 14h  🔗 3.2
- 3.4.1 `/(authenticated)/dashboard/page.tsx`.
- 3.4.2 Awaiting-approval tile, stage histogram, stuck list, throughput chart (Recharts — add as dep when starting).

### Task 3.5 — Settings slice  ⏱ 6h
- 3.5.1 `features/settings/` — WhatsApp group config (admin-only), Drive connect, notification prefs.

## ✅ Phase 3 acceptance (local)
- Dev logs show `[whatsapp:dev] would send: "new cut uploaded …"`.
- Dashboard surfaces a stuck demo project after backdating its activity.
- A Google Doc imports as Script V1 against a personal Google account.

---

# Phase 4 — Polish & Analytics  (2 weeks, ≈40–50h)

Still local. PostHog signup deferred to Phase 5 — track events to a `dev` project key or no-op in dev.

### Task 4.1 — Global search  ⏱ 12h
- Postgres FTS (`tsvector`) across projects, scripts, comments, cast. `GET /search?q=…`. cmd-K palette (shadcn Command).

### Task 4.2 — PDF export  ⏱ 8h
- `app/jobs/pdf.py` via `weasyprint`. `GET /projects/{id}/export.pdf` returns presigned GCS link once generated.

### Task 4.3 — Notion import  ⏱ 6h
- Notion OAuth + markdown conversion. (Add Notion API signup if you want to test live; otherwise mock.)

### Task 4.4 — PostHog instrumentation (dev no-op)  ⏱ 6h
- Install `posthog-js` + `posthog-python`. Wrapper modules; events fire only if `POSTHOG_KEY` is set. Phase 5 sets the key.

### Task 4.5 — Stretch: guest approval links (optional)  ⏱ 10h
- Tokenised public URL per cut. AVG-compliant.

## ✅ Phase 4 acceptance (local)
- Search finds projects, script content, cast names from cmd-K.
- PDF export of a demo project succeeds locally.
- Code paths for analytics exist but no real PostHog account yet.

---

# Phase 5 — Deployment & Go-Live  (≈40–55h, 1–1.5 weeks)

**This is the first time we touch the VPS, real external accounts, or production secrets.** Everything in Phases 0–4 was localhost.

## Task 5.1 — Production external accounts  ⏱ 6h 🛠
- 5.1.1 **GCP project** `sons-realestate-cms`, billing enabled.
- 5.1.2 **GCS bucket `sre-video-prod`** (`europe-west4`, Standard, uniform IAM, Object Versioning ON).
- 5.1.3 **GCS bucket `sre-backups`** (`europe-west4`, Coldline, 30-day lifecycle).
- 5.1.4 Service account `sre-app@…iam.gserviceaccount.com` with `Storage Object Admin` on those two buckets only. JSON key downloaded (will be placed at `/etc/sre/gcp-key.json` later).
- 5.1.5 **Resend** account + verify `sonsrealestate.nl` sender domain (SPF/DKIM DNS records).
- 5.1.6 **WhatsApp Business** Cloud API: business verification, phone number, submit message templates (review takes days — start here on day 1 of Phase 5).
- 5.1.7 Production **VAPID** keypair (new — don't reuse dev).
- 5.1.8 **Google Maps Platform** prod API key (HTTP-referrer-restricted to `*.sonsrealestate.nl/*`).
- 5.1.9 **Google Drive** OAuth client (production type, verified app — verification process can take weeks; start early).
- 5.1.10 **Sentry** project for backend + frontend.
- 5.1.11 **PostHog** production project key.

## Task 5.2 — Hostinger VPS provisioning  ⏱ 4h 🛠
- 5.2.1 Provision **Hostinger KVM 4** (4 vCPU / 16 GB RAM / 200 GB NVMe), EU datacentre (Vilnius / Frankfurt).
- 5.2.2 Ubuntu 24.04 LTS, SSH key auth only, disable root SSH password.
- 5.2.3 `deploy` user with sudo; lock root SSH.
- 5.2.4 UFW: allow 22, 80, 443; deny rest.
- 5.2.5 `fail2ban` on SSH.
- 5.2.6 `unattended-upgrades` for security patches.
- 5.2.7 4 GB swap; timezone `Europe/Amsterdam`.

## Task 5.3 — VPS runtime stack  ⏱ 3h 🛠
- 5.3.1 PostgreSQL 16 (apt), create `cms` DB + `cms_app` user, tune `postgresql.conf` for available RAM.
- 5.3.2 Redis 7 (apt), bind to `127.0.0.1`, set `requirepass`.
- 5.3.3 Node 20 (nodesource) + pnpm.
- 5.3.4 Python 3.12 (deadsnakes PPA) + `uv`.
- 5.3.5 Caddy 2 (Cloudsmith repo).

## Task 5.4 — DNS + Caddy + TLS  ⏱ 2h 🛠
- 5.4.1 DNS A records: `cms.sonsrealestate.nl`, `api.cms.sonsrealestate.nl` → VPS IP.
- 5.4.2 Deploy `infra/Caddyfile` to `/etc/caddy/Caddyfile`:
   ```
   cms.sonsrealestate.nl { reverse_proxy localhost:3000 }
   api.cms.sonsrealestate.nl { reverse_proxy localhost:8000 }
   ```
- 5.4.3 `systemctl reload caddy` → SSL auto-provisioned by Let's Encrypt.

## Task 5.5 — systemd units + secrets  ⏱ 4h 🛠
- 5.5.1 `/etc/sre/secrets.env` (root:deploy 640): all production env vars (DB URL, JWT secret, Resend API key, WhatsApp token, Sentry DSN, PostHog key, etc.).
- 5.5.2 `/etc/sre/gcp-key.json` (root:deploy 640): service-account key from 5.1.4.
- 5.5.3 `infra/systemd/sre-api.service` — uvicorn workers, `EnvironmentFile=/etc/sre/secrets.env`, `Environment=GOOGLE_APPLICATION_CREDENTIALS=/etc/sre/gcp-key.json`, restart on failure.
- 5.5.4 `infra/systemd/sre-worker.service` — arq worker.
- 5.5.5 `infra/systemd/sre-web.service` — `node .next/standalone/server.js` on :3000.
- 5.5.6 `systemctl enable --now sre-api sre-worker sre-web`.

## Task 5.6 — Production code wiring  ⏱ 4h 🐍
- 5.6.1 Real Resend SDK call in `app/services/email_service.py` when `is_prod`.
- 5.6.2 Real Meta WhatsApp API call in `app/services/whatsapp_service.py` when `is_prod`.
- 5.6.3 PostHog identify + capture wired with prod key.
- 5.6.4 Sentry SDKs initialised in `app/main.py` and `frontend/src/app/layout.tsx`.
- 5.6.5 CSP header in Caddy: `script-src 'self'`, `connect-src 'self' api.cms.sonsrealestate.nl …`.

## Task 5.7 — Deploy script + GitHub Actions  ⏱ 4h 🛠
- 5.7.1 `infra/scripts/deploy.sh` (runs on VPS):
   ```
   cd /srv/sre && git pull
   uv sync --frozen
   pnpm --filter frontend install --frozen-lockfile
   pnpm --filter frontend build
   uv run alembic upgrade head
   systemctl restart sre-api sre-worker sre-web
   ```
- 5.7.2 `infra/scripts/bootstrap-vps.sh`: idempotent first-run helper (creates `/srv/sre`, sets perms, installs systemd units, etc.).
- 5.7.3 `.github/workflows/deploy.yml`: on push to `main`, run `make lint && make test`, then SSH into VPS and run `deploy.sh`. SSH key + host in GH encrypted secrets.

## Task 5.8 — Backups  ⏱ 3h 🛠
- 5.8.1 `infra/scripts/backup.sh`: `pg_dump | gpg --encrypt --recipient backup@…` → `gcloud storage cp - gs://sre-backups/$(date +…).sql.gpg`.
- 5.8.2 `/etc/cron.daily/sre-backup` symlink.
- 5.8.3 Restore drill script: pull latest dump, decrypt, restore into scratch DB on the dev machine. Run once before go-live.

## Task 5.9 — First deploy + smoke test  ⏱ 4h 🛠
- 5.9.1 Push to `main` → GitHub Actions deploys.
- 5.9.2 `https://cms.sonsrealestate.nl` and `https://api.cms.sonsrealestate.nl/healthz` both green.
- 5.9.3 Run `scripts/create_admin.py` over SSH to bootstrap the CEO's account.
- 5.9.4 CEO logs in via magic-link from a real email (Resend delivers it).
- 5.9.5 Walk one project end-to-end: create → script → upload cut → comment → approve.
- 5.9.6 Verify push notification fires on a phone (PWA installed).
- 5.9.7 Verify WhatsApp message hits the configured group.
- 5.9.8 Verify Sentry receives a deliberate test error.
- 5.9.9 Verify PostHog receives the `stage_changed` event.

## Task 5.10 — Monitoring + go-live  ⏱ 4h 🛠
- 5.10.1 Sentry alert rules (5xx > 5/min, frontend errors > 10/min).
- 5.10.2 Uptime monitor (UptimeRobot or similar — free) on both subdomains.
- 5.10.3 PostHog funnel dashboard for time-in-stage.
- 5.10.4 Hand-off doc for the CEO: how to add users, how to read the dashboard, where to file issues.
- 5.10.5 Onboard remaining team members.

## ✅ Phase 5 acceptance
- Production CMS accessible at `https://cms.sonsrealestate.nl` with HTTPS.
- CEO + at least 2 other users onboarded.
- First real video walked end-to-end with WhatsApp + push notifications working.
- Sentry + PostHog + UptimeRobot all reporting.
- Backup ran, restore drill verified.
- WhatsApp group is notification-only; coordination has moved into the app.

---

# Phase 6+ — Future (AI, transcoding, ML)

Justifies the Python backend choice. When CEO is ready: ffmpeg-python proxy generation, Anthropic/OpenAI script suggestions, scene detection via OpenCV, Vertex AI Gemini if the team wants managed GCP AI. `app/agents/` folder added here per blueprint.

---

# Cross-cutting Engineering

## Makefile (canonical entrypoints)
```
make help          # auto-list of all targets
make bootstrap     # install + up + migrate (Phase 0 onwards)
make install       # uv sync + pnpm install
make up / down     # docker-compose
make dev           # uvicorn --reload
make dev-web       # pnpm --filter frontend dev
make dev-worker    # arq app.jobs.worker.WorkerSettings
make db-migration MSG="..."
make db-upgrade / db-downgrade
make lint          # ruff + mypy + codespell + no-raw-fetch grep + pnpm lint
make typecheck     # mypy + pnpm type-check
make test          # pytest + pnpm test
make seed          # seed_demo.py
make deploy        # Phase 5+; ssh deploy@vps "cd /srv/sre && infra/scripts/deploy.sh"
```

## Testing
- Backend: `pytest` + `pytest-asyncio` + `httpx.AsyncClient` against a test DB. Permissions matrix tests per role.
- Frontend: Vitest + RTL.
- E2E: Playwright against the docker-compose stack.

## Observability
- Phases 0–4: stdout logs + `.dev-emails/` + console WhatsApp.
- Phase 5: Sentry + PostHog + UptimeRobot + systemd journal.

## Security
- All inputs Pydantic-validated.
- `slowapi` on auth + presign endpoints.
- Magic-link & GCS presign: 15 min TTL.
- Production secrets only in `/etc/sre/secrets.env` (Phase 5) and GitHub Actions encrypted secrets.
- SSH key-only, fail2ban, UFW.
- AVG: EU VPS, EU GCS region, EU Resend region, data-subject delete endpoint.
- `sessionStorage` JWT mitigated by strict CSP from Caddy + sanitised tiptap output.

## Risk Register
| Risk | Mitigation |
|---|---|
| Scaffolding drag delays real feature work | Phase 0 capped at 12h; ship empty app and start Phase 1 immediately |
| Phase 1 plumbing creep | Strict scope: defer anything not in spec §12 |
| WhatsApp template approval >1 week | Start submission on day 1 of Phase 5 |
| Drive OAuth verification weeks-long | Submit on day 1 of Phase 5; meanwhile use unverified app for dev users (warning banner) |
| Multi-GB uploads fail mid-stream | Resumable + 2 GB cap on MVP |
| Solo-dev burnout | Internal alpha demo to CEO at week 5 of Phase 1 (auth + kanban + edits) |
| VPS single-node failure | Daily encrypted backups + documented restore runbook |
| `sessionStorage` JWT + XSS | Strict CSP (Caddy), no innerHTML-from-user, sanitize tiptap |
| Disk fills with logs | journald rotation + size cap; videos never on VPS disk |
| GCS egress cost (~€0.10/GB) | Cache playback signed URLs (15 min); Phase 5+ proxy transcodes |
| Service-account key leak | Mode 640 root:deploy, never in git, quarterly rotation |

---

# Milestone Schedule (calendar, optimistic)

| Week | Milestone |
|---|---|
| 1 | Phase 0 done — empty monorepo + docker-compose stack working |
| 1–2 | Phase 1 backend: auth + permissions + project CRUD |
| 3 | Frontend foundation + shadcn design system + kanban rendering |
| 4 | Script editor wired end-to-end |
| 5 | Edit upload + review player — **internal alpha demo to CEO** |
| 6–7 | Phase 1 polish; meet acceptance criteria |
| 8–10 | Phase 2: field features + PWA + push |
| 11–12 | Phase 3: WhatsApp (mocked) + dashboards + Drive |
| 13–14 | Phase 4: polish + analytics |
| 15 | **Phase 5: deployment week** — VPS, accounts, deploy, go-live |
| 16 | Hand-off + monitoring tuning |

---

# Day-1 Checklist (Phase 0)

1. `mkdir sons-realestate-cms && cd sons-realestate-cms && git init`.
2. Task 0.1: `uv init`, add deps, configure ruff/mypy/codespell.
3. Task 0.2: scaffold `app/main.py` + `config.py` + lifespan + `/healthz`.
4. Task 0.3: `alembic init alembic`, wire env.py, write base model.
5. Task 0.4: `pnpm create next-app@latest frontend …`, install deps, `npx shadcn init`, install primitives, write `frontend/src/lib/api-client.ts` **before any feature code**, add CI grep guard.
6. Task 0.5: write `docker-compose.yml` (postgres + redis + fake-gcs-server), `.env.example`.
7. Task 0.6: write `Makefile`, stub `email_service.py` (writes to `.dev-emails/`) + `whatsapp_service.py` (console log).
8. Task 0.7: README quickstart, `.github/workflows/ci.yml` (lint + test only — no deploy), push to GitHub.
9. Verify: `git clone`, `make bootstrap`, `make dev`, `make dev-web` — empty app reachable at `localhost:3000`, healthz at `localhost:8000/healthz`. Begin Task 1.1.
