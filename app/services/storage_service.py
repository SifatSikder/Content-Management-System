"""Object-storage service (Google Cloud Storage).

All public functions are async — the google-cloud-storage SDK is sync, so we
run it on a thread via `asyncio.to_thread`.

Resumable uploads use GCS's native protocol — the backend mints a session URL
and the client PUTs chunks to it directly. See implementation_plan.md Task 1.7.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
from functools import lru_cache

import structlog

log = structlog.get_logger(__name__)


@lru_cache(maxsize=1)
def _get_client() -> object:
    """Lazily build the GCS client.

    Returns an instance of `google.cloud.storage.Client` — typed as `object`
    so this module doesn't force an import-time dependency on the SDK for
    callers that only need the constants. Credentials are picked up from
    `GOOGLE_APPLICATION_CREDENTIALS` (a service-account JSON key path).
    """
    from google.cloud import storage as gcs

    return gcs.Client()


def _bucket(name: str) -> object:
    client = _get_client()
    return client.bucket(name)  # type: ignore[attr-defined]


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
        blob = _bucket(bucket_name).blob(object_name)  # type: ignore[attr-defined]
        url: str = blob.create_resumable_upload_session(
            content_type=content_type,
            size=size_bytes,
            origin=origin,
        )
        return url

    return await asyncio.to_thread(_sync)


async def blob_exists(*, bucket_name: str, object_name: str) -> bool:
    def _sync() -> bool:
        blob = _bucket(bucket_name).blob(object_name)  # type: ignore[attr-defined]
        exists: bool = blob.exists()
        return exists

    return await asyncio.to_thread(_sync)


async def blob_size(*, bucket_name: str, object_name: str) -> int | None:
    def _sync() -> int | None:
        blob = _bucket(bucket_name).blob(object_name)  # type: ignore[attr-defined]
        blob.reload()
        size = blob.size
        return int(size) if size is not None else None

    return await asyncio.to_thread(_sync)


async def signed_read_url(
    *,
    bucket_name: str,
    object_name: str,
    expires_in_seconds: int = 900,
    response_content_type: str | None = None,
    response_content_disposition: str | None = None,
) -> str:
    """Return a V4-signed read URL for the given object.

    `response_content_type` / `response_content_disposition` override what
    the browser sees on the response, regardless of what was stored. We use
    this for documents (PDFs, images shown in-app) so the browser renders
    inline instead of downloading — resumable uploads land with unreliable
    Content-Type, so always pass the desired response type explicitly when
    minting a URL.
    """

    def _sync() -> str:
        blob = _bucket(bucket_name).blob(object_name)  # type: ignore[attr-defined]
        url: str = blob.generate_signed_url(
            version="v4",
            expiration=_dt.timedelta(seconds=expires_in_seconds),
            method="GET",
            response_type=response_content_type,
            response_disposition=response_content_disposition,
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
