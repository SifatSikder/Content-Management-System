"""Shared pytest fixtures.

Tests run against the local docker-compose Postgres (the same DB used by
`make dev`). To stay independent of seed/dev data, each test that needs users
generates unique emails per run via the `unique_email` fixture.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import create_app
from app.models.base import get_sessionmaker


@pytest_asyncio.fixture
async def app_client() -> AsyncIterator[AsyncClient]:
    """In-process async HTTP client backed by an ASGITransport."""
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        yield session


@pytest_asyncio.fixture
def unique_email() -> str:
    """Return a fresh email guaranteed not to collide with other tests."""
    return f"pytest-{uuid.uuid4().hex[:12]}@example.com"
