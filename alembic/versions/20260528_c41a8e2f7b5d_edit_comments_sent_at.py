"""Add sent_at to edit_comments — reviewer batches comments before dispatch.

Revision ID: c41a8e2f7b5d
Revises: e7b8c1d3a5f9
Create Date: 2026-05-28 05:00:00.000000

Reviewers (CEO + Asst CEO) now draft timestamped comments locally and
only push them to the editor once they hit "Send issues to editor".
Comments with `sent_at IS NULL` are drafts visible only to their
author; once stamped they become part of the editor's feedback queue.

Existing rows backfill with `sent_at = created_at` so prior comments
stay visible to everyone (don't retroactively hide audit data).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c41a8e2f7b5d"
down_revision: Union[str, Sequence[str], None] = "e7b8c1d3a5f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "edit_comments",
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Backfill historical comments to "already sent" so they stay
    # visible to the editor — only NEW comments go through the draft
    # workflow from here on.
    op.execute("UPDATE edit_comments SET sent_at = created_at")


def downgrade() -> None:
    op.drop_column("edit_comments", "sent_at")
