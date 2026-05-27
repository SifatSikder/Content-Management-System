"""Clear submitted_at on idea_versions that have no signoffs.

Revision ID: e8b1c4f72d35
Revises: a0c2daf73d92
Create Date: 2026-05-27 22:15:00.000000

Submission semantics changed: a version is now "submitted for review"
only after the owner explicitly clicks Request feedback. Previously
every save auto-stamped `submitted_at`, so all existing draft versions
look submitted even though they were never sent out. Reviewers see
the signoff form on those drafts, which is exactly the bug we fixed.

Backfill: clear `submitted_at` on any version that has no signoffs.
Versions with signoffs were genuinely in review and stay submitted —
clearing them would invalidate ongoing reviews.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "e8b1c4f72d35"
down_revision: Union[str, None] = "a0c2daf73d92"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE idea_versions iv
        SET submitted_at = NULL
        WHERE submitted_at IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM idea_signoffs sg
              WHERE sg.idea_version_id = iv.id
          )
        """
    )


def downgrade() -> None:
    # One-way fix — restoring fabricated timestamps doesn't make sense.
    pass
