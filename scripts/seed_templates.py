"""Upsert every registered department template into `department_templates`.

Run via `make seed-templates`. Idempotent — re-running refreshes name +
description + JSONB columns for existing rows.

Phase B's data migration also writes the same rows directly so that a fresh
`make db-upgrade` on an empty DB doesn't need a separate seed step. This
script exists for two scenarios:

  * After editing `app/seeds/templates/<name>.py`, push the changes into the
    DB without writing a new Alembic migration.
  * Bootstrapping a database that for some reason missed the data migration
    (e.g. restored from a pre-Phase-B snapshot).
"""

from __future__ import annotations

import asyncio
import sys

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.logging import configure_logging
from app.models.base import get_sessionmaker
from app.models.department_template import DepartmentTemplateModel
from app.seeds.templates import all_templates

log = structlog.get_logger(__name__)


async def upsert_templates() -> int:
    """Upsert every template; returns the number of rows touched."""
    sessionmaker = get_sessionmaker()
    touched = 0
    async with sessionmaker() as session:
        for tpl in all_templates():
            stmt = pg_insert(DepartmentTemplateModel).values(
                key=tpl["key"],
                name=tpl["name"],
                description=tpl.get("description"),
                default_capabilities=tpl.get("default_capabilities", []),
                default_stages=tpl.get("default_stages", []),
                default_roles=tpl.get("default_roles", []),
                is_system=bool(tpl.get("is_system", False)),
            ).on_conflict_do_update(
                index_elements=[DepartmentTemplateModel.key],
                set_={
                    "name": tpl["name"],
                    "description": tpl.get("description"),
                    "default_capabilities": tpl.get("default_capabilities", []),
                    "default_stages": tpl.get("default_stages", []),
                    "default_roles": tpl.get("default_roles", []),
                    "is_system": bool(tpl.get("is_system", False)),
                },
            )
            await session.execute(stmt)
            touched += 1
            log.info("template_upserted", key=tpl["key"], name=tpl["name"])
        await session.commit()

        result = await session.execute(select(DepartmentTemplateModel.key))
        log.info(
            "templates_in_db",
            keys=sorted(k for (k,) in result.all()),
        )
    return touched


def main() -> None:
    from app.config import get_settings

    configure_logging(get_settings())
    touched = asyncio.run(upsert_templates())
    log.info("seed_templates_done", touched=touched)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log.exception("seed_templates_failed")
        sys.exit(1)
