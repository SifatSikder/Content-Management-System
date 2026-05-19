"""Idempotent demo seed.

Creates a working team and two demo projects so the dev environment isn't
empty after `make bootstrap`. Re-running this script is safe — it matches
users by email and projects by `(owner_email, title)` and skips existing rows.

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

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import configure_logging
from app.models.base import dispose_engine, get_sessionmaker
from app.models.enums import Category, PipelineStage, Role
from app.models.project import ProjectModel
from app.models.user import UserModel

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class SeedUser:
    email: str
    name: str
    role: Role
    locale: str = "nl"


@dataclass(frozen=True)
class SeedProject:
    title: str
    description: str
    category: Category
    stage: PipelineStage
    owner_email: str
    due_in_days: int | None


SEED_USERS: tuple[SeedUser, ...] = (
    SeedUser(email="ceo@example.com", name="Demo CEO", role=Role.CEO),
    SeedUser(
        email="director@example.com",
        name="Demo Director",
        role=Role.ASSISTANT_DIRECTOR,
    ),
    SeedUser(email="editor@example.com", name="Demo Editor", role=Role.EDITOR),
    SeedUser(email="crew@example.com", name="Demo Crew", role=Role.CREW),
)

SEED_PROJECTS: tuple[SeedProject, ...] = (
    SeedProject(
        title="Herengracht 401 — woningtour",
        description="Korte tour van het grachtenpand, focus op licht en woonkamer.",
        category=Category.PROPERTY_TOUR,
        stage=PipelineStage.SCRIPT_DRAFTING,
        owner_email="director@example.com",
        due_in_days=14,
    ),
    SeedProject(
        title="Buurtprofiel: De Pijp",
        description="Sfeerimpressie van de buurt met interviews bij twee horecazaken.",
        category=Category.NEIGHBOURHOOD,
        stage=PipelineStage.IDEA,
        owner_email="ceo@example.com",
        due_in_days=None,
    ),
)


async def _upsert_user(session: AsyncSession, seed: SeedUser) -> UserModel:
    result = await session.execute(select(UserModel).where(UserModel.email == seed.email))
    existing = result.scalar_one_or_none()
    if existing is not None:
        log.info("seed_user_exists", email=seed.email)
        return existing
    user = UserModel(email=seed.email, name=seed.name, role=seed.role, locale=seed.locale)
    session.add(user)
    await session.flush()
    log.info("seed_user_created", email=seed.email, role=seed.role.value)
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
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        users_by_email: dict[str, UserModel] = {}
        for seed_user in SEED_USERS:
            users_by_email[seed_user.email] = await _upsert_user(session, seed_user)

        for seed_project in SEED_PROJECTS:
            owner = users_by_email.get(seed_project.owner_email)
            if owner is None:
                raise RuntimeError(
                    f"Seed project owner {seed_project.owner_email!r} is not in SEED_USERS"
                )
            await _upsert_project(session, seed_project, owner)

        await session.commit()
    await dispose_engine()


def main() -> None:
    from app.config import get_settings

    configure_logging(get_settings())
    asyncio.run(_run())
    log.info("seed_complete", users=len(SEED_USERS), projects=len(SEED_PROJECTS))


if __name__ == "__main__":
    main()
