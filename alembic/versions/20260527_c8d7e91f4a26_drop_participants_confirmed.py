"""Drop participants.confirmed — replaced by Lock casting.

Revision ID: c8d7e91f4a26
Revises: b6c39d4e5a18
Create Date: 2026-05-28 00:30:00.000000

Per-row "Confirmed" toggle is redundant now that Lock casting is the
single source of truth for "the cast set is final". Drops the column +
the matching frontend/route/service handlers in the same commit.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c8d7e91f4a26"
down_revision: Union[str, Sequence[str], None] = "b6c39d4e5a18"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("participants", "confirmed")


def downgrade() -> None:
    op.add_column(
        "participants",
        sa.Column(
            "confirmed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
