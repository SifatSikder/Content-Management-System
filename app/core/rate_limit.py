"""Shared slowapi limiter + handler.

A single Limiter instance is registered on `app.state.limiter` in the app
factory; routes import `limiter` from here and decorate handlers with
`@limiter.limit("5/minute")`. The 429 response is shaped to match the rest
of the API's `{detail, request_id}` envelope.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

if TYPE_CHECKING:
    from starlette.requests import Request


limiter = Limiter(key_func=get_remote_address)


async def rate_limit_handler(request: Request, exc: Exception) -> JSONResponse:
    """Translate slowapi's `RateLimitExceeded` into our standard error envelope."""
    assert isinstance(exc, RateLimitExceeded)
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "detail": f"Rate limit exceeded: {exc.detail}",
            "request_id": request_id,
        },
    )


__all__ = ["limiter", "rate_limit_handler"]
