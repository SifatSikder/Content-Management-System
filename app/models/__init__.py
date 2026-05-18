"""SQLAlchemy ORM models.

Real entity models land in Phase 1. This package exposes only the declarative
`Base` and shared mixins for now so Alembic autogenerate has a stable target.
"""

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

__all__ = ["Base", "TimestampMixin", "UUIDPrimaryKeyMixin"]
