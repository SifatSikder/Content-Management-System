"""FastAPI routers — one module per domain. Wired in `app.main`."""

from app.routes import health

__all__ = ["health"]
