"""Object-storage service (GCS, with fake-gcs-server in dev).

All public functions are async — the google-cloud-storage SDK is sync, so we
run it on a thread via `asyncio.to_thread`. The SDK honours
`STORAGE_EMULATOR_HOST`, so the same code paths work against fake-gcs-server
in dev and the real GCS service in prod (Phase 5 only enables the prod path
by leaving the env var unset and providing service-account credentials).

Resumable uploads use GCS's native protocol — the backend mints a session URL
and the client PUTs chunks to it directly. See implementation_plan.md Task 1.7.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import os
from functools import lru_cache
from urllib.parse import quote

import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)


@lru_cache(maxsize=1)
def _get_client() -> object:
    """Lazily build the GCS client.

    Returns an instance of `google.cloud.storage.Client` — typed as `object`
    so this module doesn't force an import-time dependency on the SDK for
    callers that only need the constants.
    """
    from google.cloud import storage as gcs

    settings = get_settings()
    if settings.storage_emulator_host:
        os.environ.setdefault("STORAGE_EMULATOR_HOST", settings.storage_emulator_host)
        # The SDK needs *some* project id even against the emulator.
        return gcs.Client(project="sre-dev")
    return gcs.Client()


def _ensure_bucket(name: str) -> object:
    """Return the bucket, creating it on the emulator if it doesn't exist."""
    client = _get_client()
    bucket = client.bucket(name)  # type: ignore[attr-defined]
    settings = get_settings()
    if settings.storage_emulator_host and not bucket.exists():
        bucket = client.create_bucket(name)  # type: ignore[attr-defined]
        log.info("storage_bucket_created", bucket=name)
    return bucket


async def create_resumable_upload_session(
    *,
    bucket_name: str,
    object_name: str,
    content_type: str,
    size_bytes: int,
    origin: str | None = None,
) -> str:
    """Initiate a resumable upload and return the session URL.

    The frontend PUTs the file body to this URL with `Content-Range` headers
    per the GCS protocol. The session expires per Google's docs (7 days).
    """

    def _sync() -> str:
        bucket = _ensure_bucket(bucket_name)
        blob = bucket.blob(object_name)  # type: ignore[attr-defined]
        url: str = blob.create_resumable_upload_session(
            content_type=content_type,
            size=size_bytes,
            origin=origin,
        )
        return url

    return await asyncio.to_thread(_sync)


async def blob_exists(*, bucket_name: str, object_name: str) -> bool:
    def _sync() -> bool:
        bucket = _ensure_bucket(bucket_name)
        blob = bucket.blob(object_name)  # type: ignore[attr-defined]
        exists: bool = blob.exists()
        return exists

    return await asyncio.to_thread(_sync)


async def blob_size(*, bucket_name: str, object_name: str) -> int | None:
    def _sync() -> int | None:
        bucket = _ensure_bucket(bucket_name)
        blob = bucket.blob(object_name)  # type: ignore[attr-defined]
        blob.reload()
        size = blob.size
        return int(size) if size is not None else None

    return await asyncio.to_thread(_sync)


async def signed_read_url(
    *,
    bucket_name: str,
    object_name: str,
    expires_in_seconds: int = 900,
) -> str:
    """Return a read URL for the given object.

    Prod: V4 signed URL with the configured TTL.
    Dev (emulator): a public download URL — fake-gcs-server doesn't validate
    signatures, so V4 signing would require fake credentials. The public URL
    is good enough for browser playback in dev.
    """
    settings = get_settings()

    def _sync() -> str:
        if settings.storage_emulator_host:
            host = settings.storage_emulator_host.rstrip("/")
            # The download endpoint is `/storage/v1/b/<bucket>/o/<object>?alt=media`.
            return f"{host}/storage/v1/b/{bucket_name}/o/{quote(object_name, safe='')}?alt=media"

        bucket = _ensure_bucket(bucket_name)
        blob = bucket.blob(object_name)  # type: ignore[attr-defined]
        url: str = blob.generate_signed_url(
            version="v4",
            expiration=_dt.timedelta(seconds=expires_in_seconds),
            method="GET",
        )
        return url

    return await asyncio.to_thread(_sync)


def health_check() -> bool:
    """Sanity check: can we reach the storage backend?"""
    try:
        _get_client()
        return True
    except Exception as exc:
        log.warning("storage_health_failed", error=str(exc))
        return False


__all__ = [
    "blob_exists",
    "blob_size",
    "create_resumable_upload_session",
    "health_check",
    "signed_read_url",
]
