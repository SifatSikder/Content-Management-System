"""Backfill `shooting` stage handoff onto existing Content Creation departments.

Revision ID: d4e26b9c3f7a
Revises: f1a3b9c5e72d
Create Date: 2026-05-28 01:30:00.000000

The previous migration collapsed the three shoot stages but didn't
touch `department_stage_handoffs` — existing departments still had
rows for the now-defunct `shoot_schedule`/`shoot_in_progress`/
`shoot_done` and no row for the new `shooting` stage. That left
projects landing on `shooting` with no auto-assignees, so the
director never got pulled in and never got the kickoff email.

This migration:

  1. Drops the three obsolete handoff rows from every department.
  2. Inserts a `shooting` handoff per content_creation department,
     pointing at every local role whose key is `director` or
     `junior_director`. Both keys are listed so departments running
     either the seed default or the renamed setup wire up.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "d4e26b9c3f7a"
down_revision: Union[str, Sequence[str], None] = "f1a3b9c5e72d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Drop obsolete handoffs.
    op.execute(
        "DELETE FROM department_stage_handoffs "
        "WHERE stage_key IN ('shoot_schedule', 'shoot_in_progress', 'shoot_done')"
    )

    # 2. Seed `shooting` handoff per content_creation department,
    #    pulling local director / junior_director role ids into the
    #    JSONB array. Skips departments that already have a row
    #    (idempotent).
    op.execute(
        """
        INSERT INTO department_stage_handoffs (
            id, created_at, updated_at,
            business_id, department_id, stage_key, role_ids
        )
        SELECT
            gen_random_uuid(), now(), now(),
            d.business_id, d.id, 'shooting',
            COALESCE(
                (
                    SELECT jsonb_agg(dr.id::text)
                    FROM department_roles dr
                    WHERE dr.department_id = d.id
                      AND dr.key IN ('director', 'junior_director')
                ),
                '[]'::jsonb
            )
        FROM departments d
        WHERE d.template_key = 'content_creation'
          AND NOT EXISTS (
              SELECT 1 FROM department_stage_handoffs h
              WHERE h.department_id = d.id
                AND h.stage_key = 'shooting'
          )
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM department_stage_handoffs WHERE stage_key = 'shooting'"
    )
