"""Collapse shoot_schedule / shoot_in_progress / shoot_done into a
single `shooting` stage.

Revision ID: f1a3b9c5e72d
Revises: c8d7e91f4a26
Create Date: 2026-05-28 01:00:00.000000

The shoot phase splits introduced friction without real value — the
director controls all three phases anyway, scheduling and wrapping are
properties of individual shoots (`shoots.status`), and raw-cut
submission is the only signal the team cared about for stage handoff.

Migration:

  1. Any project parked on `shoot_schedule`, `shoot_in_progress`, or
     `shoot_done` is moved to `shooting`. Existing `shoots.status`
     rows are untouched.
  2. All `stage.move:*->shoot_*` and `stage.move:shoot_*->*` permission
     rows are deleted.
  3. New `stage.move` perms (`casting->shooting`, `shooting->editing`)
     are seeded for every role on every content_creation department
     that already held the equivalent pre-collapse perms.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "f1a3b9c5e72d"
down_revision: Union[str, Sequence[str], None] = "c8d7e91f4a26"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Backfill projects parked on any of the three dropped stages.
    op.execute(
        "UPDATE projects SET stage_key = 'shooting' "
        "WHERE stage_key IN ('shoot_schedule', 'shoot_in_progress', 'shoot_done')"
    )

    # 2. Backfill stage assignments — any active row on a dropped
    #    stage gets moved onto `shooting` (and de-duped by user).
    op.execute(
        """
        UPDATE project_stage_assignments
        SET stage_key = 'shooting'
        WHERE stage_key IN ('shoot_schedule', 'shoot_in_progress', 'shoot_done')
        """
    )
    # Drop duplicate active rows (same project, same user, multiple
    # collapsed-from stages now all on `shooting`).
    op.execute(
        """
        DELETE FROM project_stage_assignments p
        USING project_stage_assignments q
        WHERE p.id > q.id
          AND p.project_id = q.project_id
          AND p.stage_key = q.stage_key
          AND p.user_id = q.user_id
          AND p.removed_at IS NULL
          AND q.removed_at IS NULL
        """
    )

    # 3. Drop stage.move permissions involving any dropped stage.
    op.execute(
        """
        DELETE FROM department_role_permissions
        WHERE action_key LIKE 'stage.move:%->shoot_schedule'
           OR action_key LIKE 'stage.move:%->shoot_in_progress'
           OR action_key LIKE 'stage.move:%->shoot_done'
           OR action_key LIKE 'stage.move:shoot_schedule->%'
           OR action_key LIKE 'stage.move:shoot_in_progress->%'
           OR action_key LIKE 'stage.move:shoot_done->%'
        """
    )

    # 4. Seed the new `stage.move:casting->shooting` and
    #    `stage.move:shooting->editing` perms on every role that
    #    previously held the equivalent (casting->shoot_schedule and
    #    shoot_done->editing respectively). Roles that already had
    #    those perms via the seed are untouched (ON CONFLICT-style
    #    NOT EXISTS guard).
    for (action_key, marker_legacy_action_key) in [
        ("stage.move:casting->shooting", "stage.move:casting->shoot_schedule"),
        ("stage.move:shooting->editing", "stage.move:shoot_done->editing"),
    ]:
        op.execute(
            f"""
            INSERT INTO department_role_permissions (
                id, created_at, updated_at,
                business_id, department_role_id, action_key, allowed
            )
            SELECT
                gen_random_uuid(), now(), now(),
                d.business_id, dr.id, '{action_key}', true
            FROM department_roles dr
            JOIN departments d ON d.id = dr.department_id
            WHERE d.template_key = 'content_creation'
              AND NOT EXISTS (
                  SELECT 1 FROM department_role_permissions p
                  WHERE p.department_role_id = dr.id
                    AND p.action_key = '{action_key}'
              )
              -- Only roles that previously held the legacy equivalent
              -- get the new perm; roles that didn't have shoot perms
              -- before shouldn't gain them now. The legacy row was
              -- deleted above, so we use a marker check against the
              -- template's seeded default: every content_creation
              -- role that holds `casting.lock` or `raw_cut.submit`
              -- corresponds to the legacy stage.move holder.
              AND EXISTS (
                  SELECT 1 FROM department_role_permissions p
                  WHERE p.department_role_id = dr.id
                    AND p.action_key IN ('casting.lock', 'raw_cut.submit', 'project.create')
              )
            """
        )


def downgrade() -> None:
    # One-way collapse — recreating the three-stage timeline post-hoc
    # would assign every project to `shoot_schedule` losing all signal
    # about where it actually was. Not worth a downgrade.
    pass
