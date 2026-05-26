"""Drop the unused `removable` column on department_stage_handoffs.

Revision ID: 9c5b406e6fd3
Revises: df2a3b3461ce
Create Date: 2026-05-27 17:30:00.000000

The column was stored but never enforced — `StageAssigneesPopover`
always showed the remove (X) button regardless. Dropping the column
removes one source of confusion from the Handoffs tab; if we ever want
"locked" chips back, we can reintroduce as a per-chip property at
add-time rather than a stage-level rule.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "9c5b406e6fd3"
down_revision: Union[str, Sequence[str], None] = "df2a3b3461ce"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("department_stage_handoffs", "removable")


def downgrade() -> None:
    op.add_column(
        "department_stage_handoffs",
        sa.Column(
            "removable",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
