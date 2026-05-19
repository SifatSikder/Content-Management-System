"""Auth endpoints — magic-link request + verify + me.

The frontend flow:
    1. POST /auth/request-link {email} → 200 ack (even on unknown email).
    2. User opens the email, lands on the frontend `/auth/callback?token=…`.
    3. Frontend calls GET /auth/verify?token=… → {access_token, user}.
    4. Frontend stores access_token in sessionStorage (key `sre.access_token`).
    5. Subsequent requests include `Authorization: Bearer <token>`.
    6. GET /auth/me returns the current user (decoded from the JWT + DB lookup).
"""

from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import InvalidTokenError, decode_access_token, issue_access_token
from app.core.rate_limit import limiter
from app.models.base import get_session
from app.models.user import UserModel
from app.schemas.auth import (
    RequestLinkBody,
    RequestLinkResponse,
    UserPublic,
    VerifyResponse,
)
from app.services.auth_service import (
    MagicLinkAlreadyUsedError,
    MagicLinkExpiredError,
    MagicLinkNotFoundError,
    request_magic_link,
    verify_magic_link,
)

router = APIRouter(prefix="/auth", tags=["auth"])
log = structlog.get_logger(__name__)


SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post(
    "/request-link",
    response_model=RequestLinkResponse,
    status_code=status.HTTP_200_OK,
    summary="Request a magic-link email",
)
@limiter.limit("5/minute")
async def post_request_link(
    request: Request,
    body: RequestLinkBody,
    session: SessionDep,
) -> RequestLinkResponse:
    """Mint a magic-link for the given email. Returns 200 even on unknown email."""
    await request_magic_link(session, email=str(body.email), locale=body.locale)
    return RequestLinkResponse()


@router.get(
    "/verify",
    response_model=VerifyResponse,
    summary="Exchange a magic-link token for a JWT",
)
async def get_verify(
    token: Annotated[str, Query(min_length=16, max_length=256)],
    session: SessionDep,
) -> VerifyResponse:
    try:
        user, _link = await verify_magic_link(session, raw_token=token)
    except MagicLinkNotFoundError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid magic link") from exc
    except MagicLinkExpiredError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Magic link expired") from exc
    except MagicLinkAlreadyUsedError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Magic link already used") from exc

    access_token = issue_access_token(user_id=user.id, email=user.email, role=user.role)
    log.info("auth_verify_ok", user_id=str(user.id))
    return VerifyResponse(
        access_token=access_token,
        user=UserPublic.model_validate(user),
    )


@router.get("/me", response_model=UserPublic, summary="Current user from the JWT")
async def get_me(request: Request, session: SessionDep) -> UserPublic:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    token = auth_header.split(" ", 1)[1].strip()
    try:
        claims = decode_access_token(token)
    except InvalidTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc

    result = await session.execute(
        select(UserModel).where(
            UserModel.id == claims.sub,
            UserModel.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return UserPublic.model_validate(user)
