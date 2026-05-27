"""Drop the `script_review` stage; backfill perms for `script_versioning.signoff`.

Revision ID: b6c39d4e5a18
Revises: f4a92c8b1d57
Create Date: 2026-05-27 23:30:00.000000

The script flow now mirrors the idea flow: the Asst CEO drafts on
`script_drafting`, sends for review in-place via signoffs, and locking
advances straight to `casting`. The separate `script_review` stage is
gone.

Migration:

  1. Any project currently sitting on `script_review` is bumped back to
     `script_drafting` (no work loss; reviews continue via signoffs).
  2. All `stage.move:*->script_review` and `stage.move:script_review->*`
     permission rows are deleted.
  3. The new `script_versioning.signoff` action key is seeded for the
     roles that should hold it on every existing Content Creation
     department: ceo, assistant_director, junior_director, and the
     renamed roles assistant_ceo + director (the user's live setup).
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "b6c39d4e5a18"
down_revision: Union[str, Sequence[str], None] = "f4a92c8b1d57"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_SIGNOFF_ROLE_KEYS = (
    "ceo",
    "assistant_director",
    "assistant_ceo",
    "junior_director",
    "director",
)


def upgrade() -> None:
    # 1. Backfill projects parked on the now-defunct stage.
    op.execute(
        "UPDATE projects SET stage_key = 'script_drafting' "
        "WHERE stage_key = 'script_review'"
    )
    # 2. Drop stale stage.move permissions for/from script_review.
    op.execute(
        "DELETE FROM department_role_permissions "
        "WHERE action_key LIKE 'stage.move:%->script_review' "
        "   OR action_key LIKE 'stage.move:script_review->%'"
    )
    # 3. Seed the new signoff action key for the roles that should
    #    have it, on every existing content_creation department. Use
    #    INSERT ... SELECT ... ON CONFLICT DO NOTHING to stay idempotent.
    role_list = ", ".join(f"'{k}'" for k in _SIGNOFF_ROLE_KEYS)
    op.execute(
        f"""
        INSERT INTO department_role_permissions (
            id, created_at, updated_at,
            business_id, department_role_id, action_key, allowed
        )
        SELECT
            gen_random_uuid(), now(), now(),
            d.business_id, dr.id, 'script_versioning.signoff', true
        FROM department_roles dr
        JOIN departments d ON d.id = dr.department_id
        WHERE d.template_key = 'content_creation'
          AND dr.key IN ({role_list})
          AND NOT EXISTS (
              SELECT 1 FROM department_role_permissions p
              WHERE p.department_role_id = dr.id
                AND p.action_key = 'script_versioning.signoff'
          )
        """
    )


def downgrade() -> None:
    # One-way fix — we don't try to recreate the script_review stage
    # data, and removing the signoff perm wouldn't restore anything
    # useful.
    pass
