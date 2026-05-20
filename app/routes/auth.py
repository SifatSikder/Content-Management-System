"""Auth endpoints — slim surface.

Authentication moved into the Next.js layer (NextAuth v5). NextAuth signs
its session JWT with the same `JWT_SECRET` as FastAPI using HS256, so the
cookie JWT is also a valid bearer token here. This module exposes one
endpoint:

    GET /auth/me — decode the bearer JWT, look up the user, return the
    public projection. Used by server-rendered Next.js pages that want to
    re-validate the session against the backend's source of truth.

Login, password change, invitation, and password reset all live in the
frontend Route Handlers under /api/auth/*.
"""

from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import InvalidTokenError, decode_access_token
from app.models.base import get_session
from app.models.user import UserModel
from app.schemas.auth import UserPublic

router = APIRouter(prefix="/auth", tags=["auth"])
log = structlog.get_logger(__name__)


SessionDep = Annotated[AsyncSession, Depends(get_session)]


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
