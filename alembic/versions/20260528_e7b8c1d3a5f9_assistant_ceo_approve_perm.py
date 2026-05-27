"""Backfill asset_review_with_timecodes.approve onto renamed assistant_ceo role.

Revision ID: e7b8c1d3a5f9
Revises: d8f4e2a1b95c
Create Date: 2026-05-28 04:30:00.000000

The seed template grants `asset_review_with_timecodes.approve` to
`ceo` + `assistant_director`. Live departments where the admin
renamed `assistant_director` → `assistant_ceo` already have the
permission via `513147b3dbf6` (which backfilled all renamed-role
perms). But the dual-reviewer flow needs to read the perm by role
key, and `assistant_ceo` rows may not have the asset_review approve
perm if the dept was created after that earlier backfill. Top up
here to keep the dual-approval gate consistent.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "e7b8c1d3a5f9"
down_revision: Union[str, Sequence[str], None] = "d8f4e2a1b95c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO department_role_permissions (
            id, created_at, updated_at,
            business_id, department_role_id, action_key, allowed
        )
        SELECT
            gen_random_uuid(), now(), now(),
            d.business_id, dr.id,
            'asset_review_with_timecodes.approve', true
        FROM department_roles dr
        JOIN departments d ON d.id = dr.department_id
        WHERE d.template_key = 'content_creation'
          AND dr.key = 'assistant_ceo'
          AND NOT EXISTS (
              SELECT 1 FROM department_role_permissions p
              WHERE p.department_role_id = dr.id
                AND p.action_key = 'asset_review_with_timecodes.approve'
          )
        """
    )


def downgrade() -> None:
    # One-way top-up. Removing the perm could break in-flight reviews.
    pass
