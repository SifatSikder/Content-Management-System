"""Backfill permissions onto user-renamed role keys.

Revision ID: 513147b3dbf6
Revises: 9c5b406e6fd3
Create Date: 2026-05-27 19:30:00.000000

When the admin deleted the template-seeded roles `assistant_director`,
`junior_director`, and `editor` from the UI and recreated them as
`assistant_ceo`, `director`, and `editor`, the new rows started empty
(no permission_action rows). This migration grants each one the
permission set the template would assign today:

- assistant_ceo: full project lifecycle + script/cast/location/raw-cut
  locks + idea signoff/lock + every stage.move *except* publish.
- director: shoot-phase + idea signoff + script lock + every stage.move
  except publish. NO project lifecycle.
- editor: editing → edit_review + back. NO project lifecycle.

Skips any (role, action_key) that already exists, so the migration is
idempotent on partial pre-existing data.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "513147b3dbf6"
down_revision: Union[str, Sequence[str], None] = "9c5b406e6fd3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NON_PUBLISH_STAGE_MOVES: list[tuple[str, str]] = [
    ("location_scouting", "draft_idea"),
    ("draft_idea", "script_drafting"),
    ("script_drafting", "script_review"),
    ("script_review", "script_drafting"),
    ("script_drafting", "casting"),
    ("script_review", "casting"),
    ("casting", "shoot_schedule"),
    ("shoot_schedule", "shoot_in_progress"),
    ("shoot_in_progress", "shoot_done"),
    ("shoot_done", "editing"),
    ("editing", "edit_review"),
    ("edit_review", "editing"),
]


def _stage_moves(transitions: list[tuple[str, str]]) -> list[str]:
    return [f"stage.move:{f}->{t}" for f, t in transitions]


ROLE_ACTIONS: dict[str, list[str]] = {
    "assistant_ceo": [
        "project.create",
        "project.edit",
        "project.delete",
        "script_versioning.lock",
        "script_versioning.unlock",
        "asset_review_with_timecodes.approve",
        "asset_review_with_timecodes.request_changes",
        "location.lock",
        "casting.lock",
        "raw_cut.submit",
        "department.edit_handoffs",
        "idea_versioning.lock",
        "idea_versioning.signoff",
        *_stage_moves(NON_PUBLISH_STAGE_MOVES),
    ],
    "director": [
        "script_versioning.lock",
        "asset_review_with_timecodes.request_changes",
        "raw_cut.submit",
        "idea_versioning.signoff",
        *_stage_moves(NON_PUBLISH_STAGE_MOVES),
    ],
    "editor": [
        "stage.move:editing->edit_review",
        "stage.move:edit_review->editing",
    ],
}


def upgrade() -> None:
    bind = op.get_bind()

    roles = bind.execute(
        sa.text(
            """
            SELECT r.id AS role_id, r.business_id, r.key AS role_key
            FROM department_roles r
            JOIN departments d ON d.id = r.department_id
            WHERE d.template_key = 'content_creation'
              AND r.key IN ('assistant_ceo', 'director', 'editor')
            """
        )
    ).mappings().all()

    existing = {
        (row.department_role_id, row.action_key)
        for row in bind.execute(
            sa.text(
                """
                SELECT department_role_id, action_key
                FROM department_role_permissions
                """
            )
        )
    }

    inserts: list[dict[str, object]] = []
    for role in roles:
        for action_key in ROLE_ACTIONS.get(role["role_key"], []):
            if (role["role_id"], action_key) in existing:
                continue
            inserts.append(
                {
                    "department_role_id": str(role["role_id"]),
                    "business_id": str(role["business_id"]),
                    "action_key": action_key,
                    "allowed": True,
                }
            )

    if inserts:
        bind.execute(
            sa.text(
                """
                INSERT INTO department_role_permissions
                    (id, department_role_id, business_id, action_key, allowed,
                     created_at, updated_at)
                VALUES
                    (gen_random_uuid(), :department_role_id, :business_id,
                     :action_key, :allowed, now(), now())
                """
            ),
            inserts,
        )


def downgrade() -> None:
    # Drop only the rows we seeded above — keep anything the admin added.
    bind = op.get_bind()
    all_actions = sorted({a for actions in ROLE_ACTIONS.values() for a in actions})
    bind.execute(
        sa.text(
            """
            DELETE FROM department_role_permissions
            WHERE action_key = ANY(:actions)
              AND department_role_id IN (
                SELECT r.id FROM department_roles r
                JOIN departments d ON d.id = r.department_id
                WHERE d.template_key = 'content_creation'
                  AND r.key IN ('assistant_ceo', 'director', 'editor')
              )
            """
        ),
        {"actions": all_actions},
    )
