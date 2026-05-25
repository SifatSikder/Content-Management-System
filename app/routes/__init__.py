"""FastAPI routers — one module per cross-cutting domain.

Capability routers (scripts, edits, locations, casting, shoots) moved
under `app/capabilities/<key>/router.py` in Phase D and are mounted via
`app.capabilities.registry`. Only the always-on, non-capability routes
stay here.
"""

from app.routes import auth, health, projects

__all__ = ["auth", "health", "projects"]
