"""Drop shoots.gear_checklist_json — feature dropped per UX feedback.

Revision ID: e5f23a6c81d4
Revises: b7e91c4f5a23
Create Date: 2026-05-28 02:30:00.000000

The gear checklist was a vestige of the original spec that the team
never actually used in practice — the date + status + call sheet
cover the operational signal they need on the shoot card.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e5f23a6c81d4"
down_revision: Union[str, Sequence[str], None] = "b7e91c4f5a23"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("shoots", "gear_checklist_json")


def downgrade() -> None:
    op.add_column(
        "shoots",
        sa.Column(
            "gear_checklist_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
