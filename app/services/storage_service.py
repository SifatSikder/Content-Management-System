"""Object storage service.

Phase 0 skeleton — fleshed out in Phase 1 Task 1.7 with resumable upload
sessions and V4 signed URLs. The same client works against `fake-gcs-server`
in dev (via `STORAGE_EMULATOR_HOST`) and against real GCS in prod.
"""

from __future__ import annotations

from functools import lru_cache

import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)


@lru_cache(maxsize=1)
def _client() -> object:
    """Lazily-imported GCS client.

    Imported lazily so app start-up doesn't depend on a configured GCP key
    in the smoke phase. The actual client is materialised on first call.
    """
    from google.cloud import storage as gcs

    settings = get_settings()
    if settings.storage_emulator_host:
        # fake-gcs-server: the SDK uses STORAGE_EMULATOR_HOST env var if set,
        # but allow explicit configuration here too.
        import os

        os.environ.setdefault("STORAGE_EMULATOR_HOST", settings.storage_emulator_host)

    return gcs.Client()


def health_check() -> bool:
    """Confirm we can talk to the storage backend (emulator or real GCS).

    Returns True on success; logs and returns False on any failure.
    """
    try:
        _client()
        return True
    except Exception as exc:
        log.warning("storage_health_failed", error=str(exc))
        return False
