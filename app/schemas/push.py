"""Pydantic DTOs for Web Push subscribe/unsubscribe."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SubscribePushBody(BaseModel):
    """Browser-emitted PushSubscription, wire format per the W3C spec."""

    endpoint: str = Field(min_length=1)
    p256dh_key: str = Field(min_length=1)
    auth_key: str = Field(min_length=1)
    user_agent: str | None = None


class PushSubscriptionPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    endpoint: str
    user_agent: str | None
    created_at: datetime
    last_used_at: datetime | None


class VapidPublicKeyResponse(BaseModel):
    """The raw uncompressed EC point, base64url-encoded — ready for
    `PushManager.subscribe({ applicationServerKey })` after base64url-decode
    on the client.
    """

    public_key: str


__all__ = [
    "PushSubscriptionPublic",
    "SubscribePushBody",
    "VapidPublicKeyResponse",
]
