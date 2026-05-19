"""FastAPI routers — one module per domain. Wired in `app.main`."""

from app.routes import auth, edits, health, projects, scripts

__all__ = ["auth", "edits", "health", "projects", "scripts"]
