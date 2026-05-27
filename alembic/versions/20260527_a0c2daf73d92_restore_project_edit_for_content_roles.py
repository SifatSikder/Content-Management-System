"""Restore `project.edit` to director + editor roles.

Revision ID: a0c2daf73d92
Revises: 513147b3dbf6
Create Date: 2026-05-27 20:30:00.000000

Last migration stripped `project.edit` from director and editor along
with `project.create/delete`. But `project.edit` gates content actions
too (uploading edits, scheduling shoots, creating locations) — without
it the editor can't upload cuts and the director can't run shoots.

The lifecycle gates (`project.create`, `project.delete`) stay
CEO+Assistant CEO only. UI gating for project metadata edit / delete
now uses `project.create` as the signal, so non-admins still can't
rename or soft-delete projects even though they hold `project.edit`.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a0c2daf73d92"
down_revision: Union[str, Sequence[str], None] = "513147b3dbf6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    roles = bind.execute(
        sa.text(
            """
            SELECT r.id, r.business_id, r.key
            FROM department_roles r
            JOIN departments d ON d.id = r.department_id
            WHERE d.template_key = 'content_creation'
              AND r.key IN ('director', 'editor', 'junior_director')
            """
        )
    ).mappings().all()
    existing = {
        (row.department_role_id, row.action_key)
        for row in bind.execute(
            sa.text(
                "SELECT department_role_id, action_key "
                "FROM department_role_permissions "
                "WHERE action_key = 'project.edit'"
            )
        )
    }
    inserts: list[dict[str, object]] = []
    for r in roles:
        if (r["id"], "project.edit") in existing:
            continue
        inserts.append(
            {
                "department_role_id": str(r["id"]),
                "business_id": str(r["business_id"]),
                "action_key": "project.edit",
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
    op.execute(
        """
        DELETE FROM department_role_permissions
        WHERE action_key = 'project.edit'
          AND department_role_id IN (
            SELECT r.id FROM department_roles r
            JOIN departments d ON d.id = r.department_id
            WHERE d.template_key = 'content_creation'
              AND r.key IN ('director', 'editor', 'junior_director')
          )
        """
    )
