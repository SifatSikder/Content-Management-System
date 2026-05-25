"""FastAPI routers — one module per domain.

All routers (including the per-feature ones: scripts, edits, locations,
casting, shoots) live here as flat top-level modules and get mounted
directly in `app/main.py`.
"""

from app.routes import auth, health, projects

__all__ = ["auth", "health", "projects"]
