"""Queue helper — enqueue arq jobs from services.

Keep this thin. Services should call `await queue_service.enqueue("send_web_push", ...)`
rather than wrangling arq's Redis pool directly. The pool is lazy-created
once per process and reused.
"""

from __future__ import annotations

from typing import Any

import structlog
from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.config import get_settings

log = structlog.get_logger(__name__)

_pool: ArqRedis | None = None


async def _get_pool() -> ArqRedis:
    global _pool
    if _pool is None:
        _pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
    return _pool


async def enqueue(
    job_name: str,
    *args: Any,
    **kwargs: Any,
) -> str | None:
    """Enqueue an arq job. Returns the job_id or None if Redis is offline."""
    try:
        pool = await _get_pool()
        job = await pool.enqueue_job(job_name, *args, **kwargs)
        if job is None:
            # `enqueue_job` returns None when a job with `_job_id` already exists.
            return None
        return job.job_id
    except Exception as exc:
        # Don't crash a request if the queue is down — log and keep moving.
        # The request path that triggers this is best-effort (notifications);
        # we'd rather drop a notification than 500 a write.
        log.warning("queue_enqueue_failed", job_name=job_name, error=str(exc))
        return None


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None


__all__ = ["close_pool", "enqueue"]
