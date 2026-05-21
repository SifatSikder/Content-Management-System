"""Web Push job — sends a notification to a single PushSubscription.

Invoked by `app.services.push_service.notify_user`. We look up the
subscription by id (vs. passing endpoint/keys in the job args) so the
job payload stays small and the source-of-truth is the DB row.

If the push service responds with 404/410, the subscription is dead —
we delete it so the next notify_user pass doesn't re-enqueue it.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import structlog
from pywebpush import WebPushException, webpush
from sqlalchemy import select

from app.config import get_settings
from app.models.base import get_sessionmaker
from app.models.notification import PushSubscriptionModel

log = structlog.get_logger(__name__)


async def send_web_push(
    ctx: dict[str, Any],
    *,
    subscription_id: str,
    payload: dict[str, Any],
) -> None:
    settings = get_settings()
    if not settings.vapid_private_pem or not settings.vapid_subject:
        log.warning("push_skipped_no_vapid", subscription_id=subscription_id)
        return

    sub_uuid = uuid.UUID(subscription_id)
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        result = await session.execute(
            select(PushSubscriptionModel).where(PushSubscriptionModel.id == sub_uuid)
        )
        sub = result.scalar_one_or_none()
        if sub is None:
            log.info("push_subscription_gone", subscription_id=subscription_id)
            return

        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh_key, "auth": sub.auth_key},
                },
                data=json.dumps(payload),
                vapid_private_key=settings.vapid_private_pem,
                vapid_claims={"sub": settings.vapid_subject},
                ttl=60 * 60 * 24,  # 24h — drop if undelivered
            )
            log.info(
                "push_sent",
                subscription_id=subscription_id,
                user_id=str(sub.user_id),
            )
        except WebPushException as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            if status_code in (404, 410):
                # Subscription is dead — clean up so we don't keep trying.
                await session.delete(sub)
                await session.commit()
                log.info(
                    "push_subscription_pruned",
                    subscription_id=subscription_id,
                    http_status=status_code,
                )
                return
            log.warning(
                "push_send_failed",
                subscription_id=subscription_id,
                http_status=status_code,
                error=str(exc),
            )
            raise


__all__ = ["send_web_push"]
