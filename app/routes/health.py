"""Liveness / readiness endpoints (unauthenticated)."""

from __future__ import annotations

from typing import Any

import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter, status
from sqlalchemy import text

from app.config import get_settings
from app.models.base import get_sessionmaker

router = APIRouter(tags=["health"])

log = structlog.get_logger(__name__)


@router.get("/healthz")
async def healthz() -> dict[str, Any]:
    """Deep health: pings the database and Redis. Used by the load balancer."""
    settings = get_settings()
    db_ok = False
    redis_ok = False

    try:
        sessionmaker = get_sessionmaker()
        async with sessionmaker() as session:
            await session.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:
        log.warning("healthz_db_failed", error=str(exc))

    try:
        client = aioredis.from_url(settings.redis_url, socket_timeout=2)  # type: ignore[no-untyped-call]
        await client.ping()
        await client.aclose()
        redis_ok = True
    except Exception as exc:
        log.warning("healthz_redis_failed", error=str(exc))

    overall_ok = db_ok and redis_ok
    return {
        "status": "ok" if overall_ok else "degraded",
        "db": db_ok,
        "redis": redis_ok,
        "env": settings.app_env,
    }


@router.get("/readyz", status_code=status.HTTP_200_OK)
async def readyz() -> dict[str, str]:
    """Cheap liveness: app process is up."""
    return {"status": "ok"}
