"""Department-scoped notification event definitions.

Replaces the hard-coded `push_*` column set on `user_notification_prefs`
(Phase 3 design) with per-department event keys. Each department template
seeds its own set; departments can add or remove keys at runtime via the
settings UI.

Schema:
    (department_id, event_key)         unique pair
    name_i18n                          localized labels
    default_enabled                    default for opt-in/out toggle

The companion `UserNotificationPrefEventModel` stores each user's override
of a given (department, event_key); a missing row means "use the default
from this row".
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DepartmentEventDefinitionModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "department_event_definitions"
    __table_args__ = (
        UniqueConstraint(
            "department_id", "event_key", name="uq_department_event_key"
        ),
    )

    department_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Denormalised business_id mirrors the pattern used elsewhere in Phase A
    # so the shared `tenant_isolation` RLS policy filters this table without
    # a recursive join.
    business_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_key: Mapped[str] = mapped_column(String(64), nullable=False)
    name_i18n: Mapped[dict[str, str]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    default_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )


__all__ = ["DepartmentEventDefinitionModel"]
