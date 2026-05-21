"""Web Push subscription endpoints."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, status

from app.auth.dependencies import CurrentUser, SessionDep
from app.schemas.push import (
    PushSubscriptionPublic,
    SubscribePushBody,
    VapidPublicKeyResponse,
)
from app.services import push_service
from app.services.push_service import VapidNotConfiguredError

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/push", tags=["push"])


@router.get(
    "/vapid-public-key",
    response_model=VapidPublicKeyResponse,
    summary="VAPID public key as base64url raw EC point (for PushManager.subscribe)",
)
async def get_vapid_public_key() -> VapidPublicKeyResponse:
    try:
        return VapidPublicKeyResponse(public_key=push_service.vapid_public_key_b64url())
    except VapidNotConfiguredError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "VAPID keys not configured"
        ) from exc


@router.post(
    "/subscribe",
    response_model=PushSubscriptionPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Register a browser PushSubscription for the current user",
)
async def post_subscribe(
    body: SubscribePushBody, user: CurrentUser, session: SessionDep
) -> PushSubscriptionPublic:
    sub = await push_service.upsert_subscription(
        session,
        user_id=user.id,
        endpoint=body.endpoint,
        p256dh_key=body.p256dh_key,
        auth_key=body.auth_key,
        user_agent=body.user_agent,
    )
    await session.commit()
    await session.refresh(sub)
    return PushSubscriptionPublic.model_validate(sub)


@router.post(
    "/unsubscribe",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a PushSubscription by endpoint",
)
async def post_unsubscribe(
    body: SubscribePushBody, user: CurrentUser, session: SessionDep
) -> None:
    # We accept the same shape as subscribe but only use `endpoint`. The
    # browser may also call this with an expired-subscription body.
    deleted = await push_service.delete_subscription_by_endpoint(
        session, endpoint=body.endpoint
    )
    await session.commit()
    log.info(
        "push_unsubscribed", user_id=str(user.id), endpoint=body.endpoint, deleted=deleted
    )


__all__ = ["router"]
