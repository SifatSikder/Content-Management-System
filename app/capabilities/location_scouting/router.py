"""Re-export of `app/routes/locations.py` under the location_scouting capability."""

from __future__ import annotations

from app.routes.locations import locations_router, projects_router

__all__ = ["locations_router", "projects_router"]
