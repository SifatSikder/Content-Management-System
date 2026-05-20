"""Idempotent demo seed — CEO-only.

After the NextAuth pivot the seed only inserts a single user: the CEO. All
other team members are added via the in-app Team page (CEO → "Invite team
member"), so the seed has no business creating users that would conflict
with the invite acceptance flow.

CEO_EMAIL, CEO_NAME, CEO_INITIAL_PASSWORD must be set in `.env.local`. The
seed bcrypts the password, marks `must_change_password=True` so the CEO is
forced through `/change-password` on first login, and sets `accepted_at` so
the row is considered active without needing to consume an invitation token.

Demo projects are kept (one in script-drafting, one in idea) so the kanban
isn't empty on first boot; both are owned by the CEO.

Run via `make seed` or `uv run python scripts/seed_demo.py`.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

# Make the repo root importable when run as `python scripts/seed_demo.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bcrypt
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.logging import configure_logging
from app.models.base import dispose_engine, get_sessionmaker
from app.models.enums import Category, PipelineStage, Role
from app.models.project import ProjectModel
from app.models.user import UserModel

log = structlog.get_logger(__name__)

# Bcrypt's OpenBSD impl caps password at 72 bytes. Same constraint applies on
# the Next.js side (bcryptjs) — they produce cross-runtime-compatible hashes.
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_BYTES = 72


def _hash_password(plain: str) -> str:
    raw = plain.encode("utf-8")
    if len(raw) > MAX_PASSWORD_BYTES:
        raise SystemExit(
            f"CEO_INITIAL_PASSWORD is longer than {MAX_PASSWORD_BYTES} UTF-8 bytes (bcrypt cap)."
        )
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("utf-8")


@dataclass(frozen=True)
class SeedProject:
    title: str
    description: str
    category: Category
    stage: PipelineStage
    due_in_days: int | None


SEED_PROJECTS: tuple[SeedProject, ...] = (
    SeedProject(
        title="Herengracht 401 — woningtour",
        description="Korte tour van het grachtenpand, focus op licht en woonkamer.",
        category=Category.PROPERTY_TOUR,
        stage=PipelineStage.SCRIPT_DRAFTING,
        due_in_days=14,
    ),
    SeedProject(
        title="Buurtprofiel: De Pijp",
        description="Sfeerimpressie van de buurt met interviews bij twee horecazaken.",
        category=Category.NEIGHBOURHOOD,
        stage=PipelineStage.IDEA,
        due_in_days=None,
    ),
)


def _require_ceo_settings(settings: Settings) -> tuple[str, str, str]:
    if not settings.ceo_initial_password:
        raise SystemExit(
            "CEO_INITIAL_PASSWORD is not set. Add it to .env.local before running `make seed`."
        )
    if len(settings.ceo_initial_password) < MIN_PASSWORD_LENGTH:
        raise SystemExit(
            f"CEO_INITIAL_PASSWORD must be at least {MIN_PASSWORD_LENGTH} characters."
        )
    return settings.ceo_email, settings.ceo_name, settings.ceo_initial_password


async def _upsert_ceo(
    session: AsyncSession, *, email: str, name: str, password_hash: str
) -> UserModel:
    """Idempotent: if the CEO row exists, update name + rehash password.

    Updating on every seed keeps `make seed` honest after env changes — change
    CEO_INITIAL_PASSWORD in .env.local and re-run; the hash refreshes.
    """
    now = datetime.now(UTC)
    result = await session.execute(select(UserModel).where(UserModel.email == email))
    existing = result.scalar_one_or_none()
    if existing is not None:
        existing.name = name
        existing.role = Role.CEO
        existing.password_hash = password_hash
        existing.must_change_password = True
        existing.accepted_at = existing.accepted_at or now
        log.info("seed_ceo_refreshed", email=email)
        await session.flush()
        return existing

    user = UserModel(
        email=email,
        name=name,
        role=Role.CEO,
        locale="nl",
        password_hash=password_hash,
        must_change_password=True,
        accepted_at=now,
    )
    session.add(user)
    await session.flush()
    log.info("seed_ceo_created", email=email)
    return user


async def _upsert_project(
    session: AsyncSession, seed: SeedProject, owner: UserModel
) -> ProjectModel:
    result = await session.execute(
        select(ProjectModel).where(
            ProjectModel.owner_id == owner.id,
            ProjectModel.title == seed.title,
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        log.info("seed_project_exists", title=seed.title)
        return existing
    due_date: date | None = None
    if seed.due_in_days is not None:
        due_date = (datetime.now(UTC) + timedelta(days=seed.due_in_days)).date()
    project = ProjectModel(
        title=seed.title,
        description=seed.description,
        category=seed.category,
        stage=seed.stage,
        owner_id=owner.id,
        due_date=due_date,
    )
    session.add(project)
    await session.flush()
    log.info("seed_project_created", title=seed.title, stage=seed.stage.value)
    return project


async def _run() -> None:
    settings = get_settings()
    email, name, password = _require_ceo_settings(settings)
    password_hash = _hash_password(password)

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        ceo = await _upsert_ceo(session, email=email, name=name, password_hash=password_hash)
        for seed_project in SEED_PROJECTS:
            await _upsert_project(session, seed_project, ceo)
        await session.commit()
    await dispose_engine()


def main() -> None:
    configure_logging(get_settings())
    asyncio.run(_run())
    log.info("seed_complete")


if __name__ == "__main__":
    main()
