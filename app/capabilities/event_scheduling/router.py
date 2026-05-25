"""Re-export of `app/routes/shoots.py` under the event_scheduling capability."""

from __future__ import annotations

from app.routes.shoots import projects_router, shoots_router

__all__ = ["projects_router", "shoots_router"]
