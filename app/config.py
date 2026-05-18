"""Application settings — single source of truth for runtime config.

Loaded once at import time via `get_settings()` (LRU-cached). Values come from
environment variables; `.env.local` is read in dev (gitignored).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

AppEnv = Literal["dev", "prod"]


class Settings(BaseSettings):
    """Runtime configuration.

    Async URL is used by the FastAPI app via SQLAlchemy's async engine.
    Sync URL is used by Alembic for migrations.
    """

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Environment -------------------------------------------------------
    app_env: AppEnv = "dev"
    app_base_url: str = "http://localhost:3000"
    log_level: str = "INFO"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # --- Database ----------------------------------------------------------
    database_url: str = "postgresql+asyncpg://cms_app:cms_app@localhost:5433/cms"
    database_url_sync: str = "postgresql+psycopg2://cms_app:cms_app@localhost:5433/cms"

    # --- Redis -------------------------------------------------------------
    redis_url: str = "redis://:cms_redis@localhost:6379/0"

    # --- Auth / JWT --------------------------------------------------------
    jwt_secret: str = "changeme-local-dev-only"
    jwt_ttl_seconds: int = 3600  # 1 hour
    magic_link_ttl_seconds: int = 900  # 15 minutes

    # --- Storage (GCS) -----------------------------------------------------
    # In dev, point the google-cloud-storage SDK at fake-gcs-server.
    storage_emulator_host: str | None = "http://localhost:4443"
    gcs_bucket_video: str = "sre-video-dev"
    gcs_bucket_backups: str = "sre-backups-dev"
    google_application_credentials: str | None = None

    # --- Email (Resend) — dev mocks, real in Phase 5 -----------------------
    resend_api_key: str | None = None
    resend_from_email: str = "noreply@sonsrealestate.local"

    # --- WhatsApp (Cloud API) — dev mocks, real in Phase 5 -----------------
    whatsapp_token: str | None = None
    whatsapp_phone_number_id: str | None = None
    whatsapp_group_id: str | None = None

    # --- Computed flags ----------------------------------------------------
    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_dev(self) -> bool:
        return self.app_env == "dev"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_prod(self) -> bool:
        return self.app_env == "prod"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide Settings singleton."""
    return Settings()
