"""Phase 0 smoke tests. Real test suites land in Phase 1."""

from __future__ import annotations

from app.config import get_settings
from app.main import create_app


def test_settings_load() -> None:
    settings = get_settings()
    assert settings.app_env in {"dev", "prod"}
    assert settings.database_url.startswith("postgresql+asyncpg://")


def test_app_factory() -> None:
    app = create_app()
    assert app.title == "Sons Real Estate — CMS API"
