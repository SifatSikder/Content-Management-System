"""arq worker entrypoint.

Run with::

    uv run arq app.jobs.worker.WorkerSettings

or via `make dev-worker`. The worker process is intentionally separate from
the FastAPI app — they share Redis + Postgres but have independent
lifecycles, so a worker crash doesn't take the API down (and vice versa).

`WorkerSettings.functions` is the registry of every job. Adding a new task:

  1. Define `async def my_task(ctx, ...) -> ...` in `app/jobs/<feature>.py`.
  2. Import it here and append to `functions`.
  3. Schedule it from a service with `await queue_service.enqueue("my_task", ...)`.

`ctx` is an arq-provided dict with `redis`, `job_id`, `job_try`, etc. Get
a DB session inside a job with `async with get_sessionmaker()() as session`.
"""

from __future__ import annotations

from typing import Any

import structlog
from arq.connections import RedisSettings

from app.config import get_settings
from app.core.logging import configure_logging
from app.jobs import push as push_jobs
from app.models.base import dispose_engine

log = structlog.get_logger(__name__)


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    configure_logging(settings)
    log.info("arq_worker_started", env=settings.app_env)


async def shutdown(ctx: dict[str, Any]) -> None:
    await dispose_engine()
    log.info("arq_worker_stopped")


def _redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(get_settings().redis_url)


class WorkerSettings:
    """arq's entrypoint contract. `arq` reads these attributes by name."""

    functions = [
        push_jobs.send_web_push,
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = _redis_settings()
    # Job retries with exponential backoff. The defaults are reasonable but
    # we pin them so the behavior doesn't shift across arq versions.
    max_tries = 3
    job_timeout = 30  # seconds
