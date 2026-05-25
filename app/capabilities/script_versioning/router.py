"""Re-export of the existing `app/routes/scripts.py` routers under the
script_versioning capability namespace."""

from __future__ import annotations

from app.routes.scripts import projects_router, scripts_router

__all__ = ["projects_router", "scripts_router"]
