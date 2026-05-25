"""Re-export of `app/routes/edits.py` under the asset_review capability."""

from __future__ import annotations

from app.routes.edits import edits_router, projects_router

__all__ = ["edits_router", "projects_router"]
