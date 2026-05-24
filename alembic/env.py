"""Alembic environment.

Uses the SYNC database URL from `app.config` (psycopg2 driver) so migrations
run as a normal CLI process. Imports every model under `app.models` so
`target_metadata = Base.metadata` is complete for `autogenerate`.
"""

from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.config import get_settings
from app.models import Base

# --- Import every ORM module so autogenerate sees its tables. ---
# Add new imports here as new model files are created.
from app.models import activity as _activity  # noqa: F401
from app.models import business as _business  # noqa: F401
from app.models import business_membership as _business_membership  # noqa: F401
from app.models import cast_member as _cast_member  # noqa: F401
from app.models import connected_google_account as _connected_google_account  # noqa: F401
from app.models import department as _department  # noqa: F401
from app.models import department_membership as _department_membership  # noqa: F401
from app.models import department_role as _department_role  # noqa: F401
from app.models import department_role_permission as _department_role_permission  # noqa: F401
from app.models import department_stage as _department_stage  # noqa: F401
from app.models import department_template as _department_template  # noqa: F401
from app.models import edit as _edit  # noqa: F401
from app.models import location as _location  # noqa: F401
from app.models import location_photo as _location_photo  # noqa: F401
from app.models import notification as _notification  # noqa: F401
from app.models import notification_prefs as _notification_prefs  # noqa: F401
from app.models import one_time_token as _one_time_token  # noqa: F401
from app.models import project as _project  # noqa: F401
from app.models import script as _script  # noqa: F401
from app.models import shoot as _shoot  # noqa: F401
from app.models import user as _user  # noqa: F401

config = context.config
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url_sync)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no live DB connection)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
