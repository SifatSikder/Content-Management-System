"""Make raw_cut_submissions belong to a specific shoot.

Revision ID: a93f7d5c2e8b
Revises: e5f23a6c81d4
Create Date: 2026-05-28 03:00:00.000000

Each shoot now owns its raw cuts — replaces the project-level "Submit
raw cuts" CTA with a per-shoot upload section.

Adds `shoot_id` (nullable FK on delete SET NULL) on
`raw_cut_submissions`. Existing rows are backfilled to the project's
sole wrapped shoot when there's exactly one; otherwise the row stays
null (nothing to point at without guessing).

`shoot_id` stays nullable so the historical fallback rows remain
queryable and don't break existing data. New rows are validated to
non-null at the route layer.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a93f7d5c2e8b"
down_revision: Union[str, Sequence[str], None] = "e5f23a6c81d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "raw_cut_submissions",
        sa.Column("shoot_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_raw_cut_submissions_shoot_id",
        "raw_cut_submissions",
        "shoots",
        ["shoot_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_raw_cut_submissions_shoot_id",
        "raw_cut_submissions",
        ["shoot_id"],
    )
    # Backfill: only when the project has exactly one wrapped shoot,
    # bind the existing raw cut to it. Otherwise leave null.
    op.execute(
        """
        UPDATE raw_cut_submissions rc
        SET shoot_id = (
            SELECT s.id FROM shoots s
            WHERE s.project_id = rc.project_id
              AND s.status = 'wrapped'
            LIMIT 2
        )
        WHERE rc.shoot_id IS NULL
          AND (
              SELECT count(*) FROM shoots s
              WHERE s.project_id = rc.project_id
                AND s.status = 'wrapped'
          ) = 1
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_raw_cut_submissions_shoot_id", table_name="raw_cut_submissions"
    )
    op.drop_constraint(
        "fk_raw_cut_submissions_shoot_id",
        "raw_cut_submissions",
        type_="foreignkey",
    )
    op.drop_column("raw_cut_submissions", "shoot_id")
