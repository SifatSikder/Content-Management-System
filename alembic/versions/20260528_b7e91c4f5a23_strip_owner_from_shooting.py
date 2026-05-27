"""Strip the project owner from `shooting` stage assignments.

Revision ID: b7e91c4f5a23
Revises: d4e26b9c3f7a
Create Date: 2026-05-28 02:00:00.000000

Projects that locked casting *before* the `shooting` handoff was
seeded got the owner auto-assigned via the empty-handoff fallback in
`assignment_service.seed_default`. After the handoff fix the
director(s) were correctly added on subsequent (unlock + re-lock)
runs, but the stale owner row was left behind — so the Asst CEO still
sees write controls on the Shoot tab even though the rule is
"Director-only".

This one-off backfill soft-deletes the owner's assignment on any
`shooting` stage where the department now has a non-empty handoff
(i.e. somebody else is actually being asked to run the shoot). Owner
assignments are preserved where the handoff resolves to zero users —
that fallback is intentional so cards never sit unassigned.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "b7e91c4f5a23"
down_revision: Union[str, Sequence[str], None] = "d4e26b9c3f7a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE project_stage_assignments psa
        SET removed_at = now()
        FROM projects p
        JOIN department_stage_handoffs h ON h.department_id = p.department_id
        WHERE psa.project_id = p.id
          AND psa.user_id = p.owner_id
          AND psa.stage_key = 'shooting'
          AND psa.removed_at IS NULL
          AND h.stage_key = 'shooting'
          AND jsonb_array_length(h.role_ids) > 0
        """
    )


def downgrade() -> None:
    # Not reversible — we'd need to know which rows the migration
    # cleared. The fallback behaviour will re-add the owner on the
    # next stage transition if the handoff is empty.
    pass
