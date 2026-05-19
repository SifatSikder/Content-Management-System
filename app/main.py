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
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestIDMiddleware
from app.core.rate_limit import limiter, rate_limit_handler
from app.models.base import dispose_engine, get_sessionmaker
from app.routes import auth, edits, health, projects, scripts

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
        title="Sons Real Estate — CMS API",
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
    app.add_middleware(RequestIDMiddleware)

    register_exception_handlers(app)

    # Rate limiting (slowapi)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

    # Routers.
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(projects.router)
    app.include_router(scripts.projects_router)
    app.include_router(scripts.scripts_router)
    app.include_router(edits.projects_router)
    app.include_router(edits.edits_router)

    return app


app = create_app()
