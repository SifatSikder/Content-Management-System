"""Business-context middleware + RLS-aware session dependency (Phase A).

Atlas hosts multiple businesses behind a single Postgres DB. Every
business-scoped table carries `business_id` + an RLS policy:

    USING (business_id = current_setting('app.current_business_id', true)::uuid
           OR current_setting('app.is_super_admin', true) = 'true')

This module owns the request-scoped wiring that makes the policy do its
job:

  1. `BusinessContextMiddleware` runs early per-request, decodes the bearer
     JWT (best-effort), resolves the *requested* business_id from the URL
     path / `X-Business-Id` header / JWT claim, validates membership for
     non-CEO users, and stashes both values on `request.state`.

  2. `business_scoped_session` is a FastAPI dependency that yields an
     `AsyncSession` with `SET LOCAL app.current_business_id = …` and
     `SET LOCAL app.is_super_admin = …` already applied. Routes import
     this via `app.auth.dependencies.SessionDep` and get RLS for free.

Phase-A note: the CEO super-admin (`user.role == Role.CEO`) always has
`is_super_admin=true`, so legacy real-estate data with `business_id IS NULL`
stays visible until Phase B backfills.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import AsyncIterator

import structlog
from fastapi import Request
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.auth.jwt import InvalidTokenError, decode_access_token
from app.models.base import get_session, get_sessionmaker
from app.models.business_membership import BusinessMembershipModel
from app.models.enums import BusinessMembershipStatus, Role
from app.models.user import UserModel

log = structlog.get_logger(__name__)

# Path prefixes for which we skip context setup entirely (no business in
# scope, no auth needed, or auth handled inside the route itself).
SKIP_PATH_PREFIXES = (
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/push/vapid-public-key",
)

# Matches the first /businesses/<uuid> segment in a URL path. Used to pull
# business_id from RESTful URLs like /businesses/{id}/departments.
_BUSINESS_PATH_RE = re.compile(
    r"^/businesses/(?P<bid>[0-9a-fA-F-]{36})(?:/|$)"
)


def _parse_uuid(value: str | None) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


def _business_id_from_path(path: str) -> uuid.UUID | None:
    match = _BUSINESS_PATH_RE.match(path)
    if match is None:
        return None
    return _parse_uuid(match.group("bid"))


class BusinessContextMiddleware(BaseHTTPMiddleware):
    """Resolve `(current_business_id, is_super_admin)` per request.

    Order of precedence for business_id (first non-None wins):
      1. `/businesses/{uuid}/...` URL path segment
      2. `X-Business-Id` request header
      3. (Future: `business_id` claim on the bearer JWT — Phase A6 wiring)

    For non-CEO users with a business_id present, the middleware checks
    `business_memberships` for an `active` row and returns 403 on mismatch.
    Missing/invalid bearer tokens are not the middleware's concern — the
    route's `current_user` dependency will surface a clean 401.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path

        # Default: anonymous, no business context. Routes that need auth
        # will surface 401 themselves via `current_user`.
        request.state.current_business_id = None
        request.state.is_super_admin = False
        request.state.current_user_id = None
        request.state.current_user_role = None

        if any(path.startswith(prefix) for prefix in SKIP_PATH_PREFIXES):
            return await call_next(request)

        user = await self._user_from_bearer(request)
        if user is None:
            # Unauthenticated request — leave state empty, let the route
            # decide. If the route requires auth it'll 401.
            return await call_next(request)

        request.state.current_user_id = user.id
        request.state.current_user_role = user.role
        is_super_admin = user.role == Role.CEO
        request.state.is_super_admin = is_super_admin

        # Resolve business_id from path → header → (future) JWT.
        bid = _business_id_from_path(path)
        if bid is None:
            bid = _parse_uuid(request.headers.get("X-Business-Id"))

        if bid is not None and not is_super_admin:
            # Non-CEO must be an active member of the targeted business.
            allowed = await self._user_is_active_member(user.id, bid)
            if not allowed:
                log.warning(
                    "business_context_denied",
                    user_id=str(user.id),
                    user_role=user.role.value,
                    business_id=str(bid),
                )
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "Not a member of this business",
                        "request_id": getattr(request.state, "request_id", None),
                    },
                )

        request.state.current_business_id = bid
        return await call_next(request)

    async def _user_from_bearer(self, request: Request) -> UserModel | None:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.lower().startswith("bearer "):
            return None
        token = auth_header.split(" ", 1)[1].strip()
        try:
            claims = decode_access_token(token)
        except InvalidTokenError:
            return None

        sessionmaker = get_sessionmaker()
        async with sessionmaker() as session:
            # Bypass RLS for this lookup — the middleware can't have set
            # `app.current_business_id` yet (chicken-and-egg). Membership
            # checks immediately after this call enforce isolation.
            await session.execute(text("SET LOCAL app.is_super_admin = 'true'"))
            result = await session.execute(
                select(UserModel).where(
                    UserModel.id == claims.sub,
                    UserModel.deleted_at.is_(None),
                )
            )
            return result.scalar_one_or_none()

    async def _user_is_active_member(
        self, user_id: uuid.UUID, business_id: uuid.UUID
    ) -> bool:
        sessionmaker = get_sessionmaker()
        async with sessionmaker() as session:
            await session.execute(text("SET LOCAL app.is_super_admin = 'true'"))
            result = await session.execute(
                select(BusinessMembershipModel.id).where(
                    BusinessMembershipModel.user_id == user_id,
                    BusinessMembershipModel.business_id == business_id,
                    BusinessMembershipModel.status == BusinessMembershipStatus.ACTIVE,
                )
            )
            return result.first() is not None


async def business_scoped_session(request: Request) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yield a session with RLS variables applied.

    Wraps `get_session` from `app.models.base` and applies `SET LOCAL` for
    `app.current_business_id` and `app.is_super_admin` based on what the
    middleware stashed on `request.state`. Use this *instead of*
    `get_session` for any route that touches a business-scoped table — the
    canonical `SessionDep` alias in `app.auth.dependencies` already points
    here, so most routes get it implicitly.
    """
    bid = getattr(request.state, "current_business_id", None)
    is_super_admin = getattr(request.state, "is_super_admin", False)

    async for session in get_session():
        # `SET LOCAL` would be ideal (transaction-scoped, auto-reset) but
        # SQLAlchemy can issue multiple transactions during a single
        # request (autoflush on commit, `session.refresh()` after a write,
        # etc.). Each subsequent transaction starts with the GUCs cleared,
        # which makes RLS unpredictable. Use session-scoped `SET` instead
        # and `RESET` on cleanup so the next pool borrower starts fresh.
        # `SET ROLE atlas_app` also persists across transactions on this
        # connection, which is what we want.
        await session.execute(text("SET ROLE atlas_app"))
        if is_super_admin:
            await session.execute(text("SET app.is_super_admin = 'true'"))
        if bid is not None:
            # bid is validated as `uuid.UUID` upstream — no injection.
            await session.execute(
                text(f"SET app.current_business_id = '{bid}'")
            )
        try:
            yield session
        finally:
            # Reset everything we touched so the connection returns to the
            # pool in a clean state for the next request.
            try:
                await session.execute(text("RESET app.current_business_id"))
                await session.execute(text("RESET app.is_super_admin"))
                await session.execute(text("RESET ROLE"))
            except Exception:
                # If the session/connection is already invalidated (e.g.
                # the request raised mid-transaction), just let it close.
                pass


__all__ = [
    "BusinessContextMiddleware",
    "business_scoped_session",
]
