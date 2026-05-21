"""Application settings — single source of truth for runtime config.

Loaded once at import time via `get_settings()` (LRU-cached). Values come from
environment variables; `.env.local` is read in dev (gitignored).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field, field_validator
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
    # IMPORTANT: NextAuth (frontend/auth.ts) signs its session JWT with this
    # same secret using HS256. Cookie JWT == valid bearer token for FastAPI.
    jwt_secret: str = "changeme-local-dev-only"
    jwt_ttl_seconds: int = 3600  # 1 hour — matches NextAuth session maxAge.

    # --- One-time tokens (invitations + password resets) -------------------
    invitation_ttl_seconds: int = 7 * 24 * 3600  # 7 days
    password_reset_ttl_seconds: int = 3600  # 1 hour

    # --- CEO bootstrap (read by scripts/seed_demo.py) ----------------------
    ceo_email: str = "ceo@example.com"
    ceo_name: str = "Demo CEO"
    ceo_initial_password: str | None = None  # required at seed time

    # --- Storage (GCS) -----------------------------------------------------
    # Credentials are picked up from GOOGLE_APPLICATION_CREDENTIALS (a
    # service-account JSON key path). Dev and prod both talk to real GCS;
    # use a separate dev bucket (e.g. with a 7-day lifecycle rule) to keep
    # cost low and avoid leaking dev assets into the prod bucket.
    gcs_bucket_video: str = "sre-video-dev"
    gcs_bucket_assets: str = "sre-assets-dev"  # location photos, cast release forms, call sheets
    gcs_bucket_backups: str = "sre-backups-dev"
    google_application_credentials: str | None = None

    # --- Gmail send (used by Phase-3 backend notifications; Next.js layer
    # owns invite + reset email sending in Phase 1) -------------------------
    gmail_oauth_client_id: str | None = None
    gmail_oauth_client_secret: str | None = None
    gmail_oauth_refresh_token: str | None = None
    gmail_sender_address: str | None = None

    # --- Google Drive OAuth (per-user; Phase 3 Task 3.3) -------------------
    # Separate OAuth client from sign-in. Scope: drive.readonly. Refresh
    # tokens are encrypted with TOKEN_ENCRYPTION_KEY (Fernet) before persist.
    google_drive_client_id: str | None = None
    google_drive_client_secret: str | None = None
    google_drive_redirect_uri: str = "http://localhost:8000/auth/google/drive/callback"
    google_drive_post_auth_redirect: str = "http://localhost:3000/settings"

    # --- Token encryption (Phase 3) ----------------------------------------
    # Fernet key (urlsafe-base64-encoded 32 bytes). Generate with
    # `uv run python scripts/gen_token_encryption_key.py`.
    token_encryption_key: str | None = None

    # --- Web Push (VAPID) --------------------------------------------------
    # Generate with `uv run python scripts/gen_vapid_keys.py`. Private key
    # is the PEM of an EC P-256 keypair; public key is the matching PEM.
    # The frontend reads the public key (as base64url raw EC point) from
    # GET /push/vapid-public-key.
    vapid_private_pem: str | None = None
    vapid_public_pem: str | None = None
    vapid_subject: str | None = None  # e.g. "mailto:ceo@example.com"

    @field_validator("vapid_private_pem", "vapid_public_pem", mode="before")
    @classmethod
    def _decode_pem(cls, value: object) -> object:
        """Tolerate `\\n`-escaped + quoted PEMs that come via the Makefile.

        `Makefile` does `include .env.local; export`, which passes our PEM
        values into the subprocess environment with literal quotes and
        `\\n` escapes (Make doesn't interpret either). pydantic-settings
        reads os.environ first, so we'd see the broken form. Normalise
        here: strip optional wrapping quotes and decode `\\n` → newline.
        """
        if not isinstance(value, str):
            return value
        v = value.strip()
        if (v.startswith('"') and v.endswith('"')) or (
            v.startswith("'") and v.endswith("'")
        ):
            v = v[1:-1]
        return v.replace("\\n", "\n")

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
