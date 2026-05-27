"""Participant model — discriminated union of cast members + sales leads.

Phase C renamed the underlying table from `cast_members` to `participants`
and added a `kind` discriminator (`"cast" | "lead"`). The same row shape
serves both Content Creation's casting tab and Marketing's lead-list tab
— the frontend renders different fields based on the department's
`participant_roster` capability config (`kind` + `visible_fields`).

The class name `CastMemberModel` is preserved as an alias of
`ParticipantModel` so existing imports across services + routes don't
have to change in one go; Phase D renames them.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ParticipantModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "participants"

    business_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Discriminator: which capability config a row was created under.
    # Defaults to "cast" on the DB side so the Phase B migration leaves
    # existing Content Creation rows correctly tagged.
    kind: Mapped[str] = mapped_column(
        String(16), nullable=False, default="cast", server_default="cast"
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    role_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # GCS object name for the signed release-form file (cast mode only).
    release_form_object_name: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Lead-mode-only fields. NULL on cast rows.
    source: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


# Backwards-compat alias — `cast_service.py`, `casting.py`, and other call
# sites still import `CastMemberModel`. Phase D renames them.
CastMemberModel = ParticipantModel


__all__ = ["CastMemberModel", "ParticipantModel"]
