"""FastAPI application factory + lifespan."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from app.config import Settings, get_settings
from app.core.business_context import BusinessContextMiddleware
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestIDMiddleware
from app.core.rate_limit import limiter, rate_limit_handler
from app.models.base import dispose_engine, get_sessionmaker
from app.routes import (
    asset_review_with_timecodes,
    auth,
    business_memberships,
    businesses,
    dashboard,
    department_handoffs,
    department_memberships,
    department_role_permissions,
    department_roles,
    departments,
    drive,
    event_scheduling,
    health,
    idea_versioning,
    location_scouting,
    me,
    notification_prefs,
    participant_roster,
    project_assignments,
    projects,
    push,
    raw_cuts,
    script_versioning,
)

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Run once on start-up, once on shutdown.

    Start-up:
      * warm the async DB pool (fail fast if DB unreachable)
      * validate settings (Pydantic does this at import, but we log the env)
    Shutdown:
      * dispose the engine
    """
    settings: Settings = get_settings()
    log.info(
        "app_startup",
        env=settings.app_env,
        base_url=settings.app_base_url,
    )

    # Warm DB pool — surface bad DB URLs immediately.
    try:
        sessionmaker = get_sessionmaker()
        async with sessionmaker() as session:
            await session.execute(text("SELECT 1"))
        log.info("db_pool_warm_ok")
    except Exception as exc:
        log.error("db_pool_warm_failed", error=str(exc))
        # Don't crash on dev — but make the failure visible.
        if settings.is_prod:
            raise

    yield

    await dispose_engine()
    log.info("app_shutdown")


def create_app() -> FastAPI:
    """Build the FastAPI app."""
    settings = get_settings()
    configure_logging(settings)

    app = FastAPI(
        title="Atlas API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.is_dev else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.is_dev else None,
    )

    # Middleware (order matters: outermost first).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(BusinessContextMiddleware)
    app.add_middleware(RequestIDMiddleware)

    register_exception_handlers(app)

    # Rate limiting (slowapi)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

    # --- Core routers ---------------------------------------------------
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(projects.router)
    app.include_router(project_assignments.router)
    app.include_router(push.router)
    app.include_router(drive.auth_router)
    app.include_router(drive.projects_router)
    app.include_router(drive.files_router)
    app.include_router(dashboard.router)
    app.include_router(notification_prefs.router)

    # --- Atlas multi-business scaffolding (Phase A) ---------------------
    app.include_router(businesses.router)
    app.include_router(business_memberships.router)
    app.include_router(departments.business_router)
    app.include_router(departments.department_router)
    app.include_router(department_roles.router)
    app.include_router(department_role_permissions.router)
    app.include_router(department_handoffs.router)
    app.include_router(department_memberships.router)
    app.include_router(me.router)

    # --- Per-template feature routers ------------------------------------
    # Mounted unconditionally; the frontend's tab routing decides which UI
    # surfaces are reachable per department template (see
    # frontend/src/features/projects/lib/projectTabs.ts). RLS + dept
    # membership still protect data on the backend.
    app.include_router(script_versioning.projects_router)
    app.include_router(script_versioning.scripts_router)
    app.include_router(idea_versioning.router)
    app.include_router(asset_review_with_timecodes.projects_router)
    app.include_router(asset_review_with_timecodes.edits_router)
    app.include_router(location_scouting.projects_router)
    app.include_router(location_scouting.locations_router)
    app.include_router(participant_roster.projects_router)
    app.include_router(participant_roster.cast_router)
    app.include_router(event_scheduling.projects_router)
    app.include_router(event_scheduling.shoots_router)
    app.include_router(raw_cuts.projects_router)

    return app


app = create_app()
