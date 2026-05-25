"""Web Push service.

Owns:
  * subscribe / unsubscribe / lookup of PushSubscriptionModel rows
  * VAPID public-key derivation (PEM → base64url raw EC point) for the
    frontend's `PushManager.subscribe({ applicationServerKey })` call
  * fan-out — `notify_user(user_id, payload)` enqueues a push job per
    active subscription. The actual HTTP delivery happens in
    `app.jobs.push.send_web_push` inside the arq worker.
"""

from __future__ import annotations

import base64
import uuid
from collections.abc import Sequence
from typing import Any

import structlog
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.notification import PushSubscriptionModel
from app.services import notification_prefs_service, queue_service

log = structlog.get_logger(__name__)


class VapidNotConfiguredError(RuntimeError):
    """Raised when VAPID env vars are missing — pushes can't be sent."""


def vapid_public_key_b64url() -> str:
    """Return the VAPID public key as a base64url-encoded raw uncompressed
    EC point — the format `applicationServerKey` expects.
    """
    settings = get_settings()
    if not settings.vapid_public_pem:
        raise VapidNotConfiguredError("VAPID_PUBLIC_PEM is not set")
    pub = serialization.load_pem_public_key(settings.vapid_public_pem.encode())
    if not isinstance(pub, ec.EllipticCurvePublicKey):
        raise VapidNotConfiguredError("VAPID public key is not an EC key")
    raw = pub.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


async def upsert_subscription(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    endpoint: str,
    p256dh_key: str,
    auth_key: str,
    user_agent: str | None,
) -> PushSubscriptionModel:
    """Idempotent subscribe: keyed on `endpoint` (browser-generated, unique
    per device + per subscribe() call). If a row exists with this endpoint
    we just refresh the keys + user_agent in case the browser re-subscribed.
    """
    existing_q = await session.execute(
        select(PushSubscriptionModel).where(PushSubscriptionModel.endpoint == endpoint)
    )
    sub = existing_q.scalar_one_or_none()
    if sub is None:
        sub = PushSubscriptionModel(
            user_id=user_id,
            endpoint=endpoint,
            p256dh_key=p256dh_key,
            auth_key=auth_key,
            user_agent=user_agent,
        )
        session.add(sub)
        await session.flush()
        log.info("push_subscription_created", subscription_id=str(sub.id))
        return sub

    sub.user_id = user_id
    sub.p256dh_key = p256dh_key
    sub.auth_key = auth_key
    sub.user_agent = user_agent
    return sub


async def delete_subscription_by_endpoint(session: AsyncSession, *, endpoint: str) -> int:
    rows = await session.execute(
        select(PushSubscriptionModel).where(PushSubscriptionModel.endpoint == endpoint)
    )
    subs = list(rows.scalars().all())
    for sub in subs:
        await session.delete(sub)
    return len(subs)


async def list_subscriptions_for_user(
    session: AsyncSession, *, user_id: uuid.UUID
) -> Sequence[PushSubscriptionModel]:
    result = await session.execute(
        select(PushSubscriptionModel).where(PushSubscriptionModel.user_id == user_id)
    )
    return list(result.scalars().all())


async def notify_user(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    payload: dict[str, Any],
    event_key: str | None = None,
    department_id: uuid.UUID | None = None,
) -> int:
    """Enqueue a push job per active subscription. Returns the count
    enqueued. Best-effort — Redis failures don't raise here (handled by
    queue_service.enqueue).

    When `event_key` AND `department_id` are provided, the user's
    notification preference for that `(department, event)` pair gates
    delivery — a muted event returns 0 without touching Redis. Callers
    that omit either argument (e.g. ad-hoc test pings, cross-department
    system notifications) bypass the gate entirely.
    """
    if event_key is not None and department_id is not None:
        enabled = await notification_prefs_service.is_event_enabled(
            session,
            user_id=user_id,
            department_id=department_id,
            event_key=event_key,
        )
        if not enabled:
            log.info(
                "push_skipped_muted",
                user_id=str(user_id),
                department_id=str(department_id),
                event_key=event_key,
            )
            return 0

    subs = await list_subscriptions_for_user(session, user_id=user_id)
    enqueued = 0
    for sub in subs:
        job_id = await queue_service.enqueue(
            "send_web_push",
            subscription_id=str(sub.id),
            payload=payload,
        )
        if job_id is not None:
            enqueued += 1
    return enqueued


__all__ = [
    "VapidNotConfiguredError",
    "delete_subscription_by_endpoint",
    "list_subscriptions_for_user",
    "notify_user",
    "upsert_subscription",
    "vapid_public_key_b64url",
]
