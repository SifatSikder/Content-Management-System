# Sons Real Estate — Content Production CRM
# Canonical entrypoint for all dev workflows. See `make help`.

SHELL := /bin/bash
.DEFAULT_GOAL := help

# Use a local .env.local when it exists so common shell invocations pick it up.
ifneq (,$(wildcard .env.local))
include .env.local
export
endif

.PHONY: help
help: ## show this help
	@awk 'BEGIN {FS = ":.*## "; printf "Targets:\n"} \
	/^[a-zA-Z_-]+:.*## / {printf "  %-18s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# --- Bootstrap --------------------------------------------------------------

.PHONY: bootstrap
bootstrap: install up db-upgrade ## first-time setup: install deps, start stack, migrate

.PHONY: install
install: ## install python + node deps
	uv sync
	cd frontend && pnpm install

# --- Docker stack -----------------------------------------------------------

.PHONY: up
up: ## start postgres + redis + fake-gcs-server
	docker compose up -d

.PHONY: down
down: ## stop the docker stack
	docker compose down

.PHONY: logs
logs: ## tail docker-compose logs
	docker compose logs -f

# --- Backend dev ------------------------------------------------------------

.PHONY: dev
dev: ## run FastAPI with --reload
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

.PHONY: dev-worker
dev-worker: ## run arq worker (Phase 2+)
	@echo "arq worker is stubbed until Phase 2 (Task 2.2)."

# --- Frontend dev -----------------------------------------------------------

.PHONY: dev-web
dev-web: ## run Next.js dev server
	cd frontend && pnpm dev

.PHONY: build-web
build-web: ## production build of the frontend
	cd frontend && pnpm build

# --- Alembic ----------------------------------------------------------------

.PHONY: db-migration
db-migration: ## create a new autogenerate migration: make db-migration MSG="add foo"
	@if [ -z "$(MSG)" ]; then echo "MSG=\"...\" is required"; exit 1; fi
	uv run alembic revision --autogenerate -m "$(MSG)"

.PHONY: db-upgrade
db-upgrade: ## apply all pending migrations
	uv run alembic upgrade head

.PHONY: db-downgrade
db-downgrade: ## roll back one migration
	uv run alembic downgrade -1

# --- Quality gates ----------------------------------------------------------

.PHONY: lint
lint: ## ruff + codespell + frontend lint + no-raw-fetch guard
	uv run ruff check .
	uv run codespell
	./scripts/check-no-raw-fetch.sh
	cd frontend && pnpm lint

.PHONY: fmt
fmt: ## auto-format python + frontend
	uv run ruff check . --fix
	uv run ruff format .

.PHONY: typecheck
typecheck: ## mypy on backend + tsc on frontend
	uv run mypy app
	cd frontend && pnpm tsc --noEmit

.PHONY: test
test: ## pytest backend + frontend tests (when present)
	uv run pytest

# --- Seed / one-offs --------------------------------------------------------

.PHONY: seed
seed: ## seed demo data (idempotent) — Phase 1+
	@echo "seed_demo.py lands in Phase 1 Task 1.2.6."

# --- Deployment (Phase 5) ---------------------------------------------------

.PHONY: deploy
deploy: ## ssh to VPS and run deploy.sh — Phase 5
	@echo "Deployment is Phase 5. See implementation_plan.md Task 5.8."
