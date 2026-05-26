"""Phase 4 of board-flow rework: department_slot_mappings + department_stage_handoffs.

Revision ID: 863ba5cb3f3a
Revises: 7d233b494bb6
Create Date: 2026-05-27 15:00:00.000000

Introduces the slot abstraction:

- `department_slot_mappings(department_id, slot_key, department_role_id)` —
  maps each logical actor slot (`OWNER`, `CEO`, `DIRECTOR`, `EDITOR` for
  Content Creation) to one of the department's roles.
- `department_stage_handoffs(department_id, stage_key, slot_keys[],
  removable)` — declares which slot(s) get auto-assigned when a project
  enters each stage.

Both tables carry a denormalised `business_id` so they share the
standard `tenant_isolation` RLS policy.

For every existing Content Creation department, this migration seeds:
  - one slot mapping per template-default slot whose role key still
    exists in the department (NULL mappings are skipped — the UI will
    surface a "slot mapping required" banner);
  - one handoff row per template-default stage.
"""

from __future__ import annotations

from typing import Any, Sequence, Union

import sqlalchemy as sa
from alembic import op

# Constants inlined: this migration historically pulled them from
# `app/seeds/templates/_slots.py`, but the slot layer was collapsed in
# revision df2a3b3461ce and that module was deleted. The values below
# are frozen at the point this migration originally ran.
DEFAULT_SLOT_ROLE_KEYS: dict[str, dict[str, str]] = {
    "content_creation": {
        "OWNER": "assistant_director",
        "CEO": "ceo",
        "DIRECTOR": "junior_director",
        "EDITOR": "editor",
    },
    "marketing": {},
}

DEFAULT_STAGE_HANDOFFS: dict[str, list[dict[str, object]]] = {
    "content_creation": [
        {"stage_key": "location_scouting", "slot_keys": ["OWNER"], "removable": True},
        {"stage_key": "draft_idea", "slot_keys": ["OWNER", "CEO", "DIRECTOR"], "removable": True},
        {"stage_key": "script_drafting", "slot_keys": ["OWNER"], "removable": True},
        {"stage_key": "script_review", "slot_keys": ["OWNER", "CEO"], "removable": True},
        {"stage_key": "casting", "slot_keys": ["OWNER"], "removable": True},
        {"stage_key": "shoot_schedule", "slot_keys": ["DIRECTOR"], "removable": True},
        {"stage_key": "shoot_in_progress", "slot_keys": ["DIRECTOR"], "removable": True},
        {"stage_key": "shoot_done", "slot_keys": ["DIRECTOR"], "removable": True},
        {"stage_key": "editing", "slot_keys": ["EDITOR"], "removable": True},
        {"stage_key": "edit_review", "slot_keys": ["OWNER", "CEO"], "removable": True},
    ],
    "marketing": [],
}

revision: str = "863ba5cb3f3a"
down_revision: Union[str, Sequence[str], None] = "7d233b494bb6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


POLICY_NAME = "tenant_isolation"
POLICY_USING_EXPR = (
    "business_id = NULLIF(current_setting('app.current_business_id', true), '')::uuid "
    "OR current_setting('app.is_super_admin', true) = 'true'"
)


def upgrade() -> None:
    # --- department_slot_mappings -----------------------------------------
    op.create_table(
        "department_slot_mappings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("department_id", sa.UUID(), nullable=False),
        sa.Column("slot_key", sa.String(length=64), nullable=False),
        sa.Column("department_role_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["department_role_id"], ["department_roles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "department_id", "slot_key", name="uq_department_slot_mapping"
        ),
    )
    op.create_index(
        "ix_department_slot_mappings_business_id",
        "department_slot_mappings",
        ["business_id"],
    )
    op.create_index(
        "ix_department_slot_mappings_department_id",
        "department_slot_mappings",
        ["department_id"],
    )

    op.execute("ALTER TABLE department_slot_mappings ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE department_slot_mappings FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {POLICY_NAME} ON department_slot_mappings "
        f"USING ({POLICY_USING_EXPR})"
    )

    # --- department_stage_handoffs ----------------------------------------
    op.create_table(
        "department_stage_handoffs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("department_id", sa.UUID(), nullable=False),
        sa.Column("stage_key", sa.String(length=120), nullable=False),
        sa.Column(
            "slot_keys",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "removable",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "department_id", "stage_key", name="uq_department_stage_handoff"
        ),
    )
    op.create_index(
        "ix_department_stage_handoffs_business_id",
        "department_stage_handoffs",
        ["business_id"],
    )
    op.create_index(
        "ix_department_stage_handoffs_department_id",
        "department_stage_handoffs",
        ["department_id"],
    )

    op.execute("ALTER TABLE department_stage_handoffs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE department_stage_handoffs FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {POLICY_NAME} ON department_stage_handoffs "
        f"USING ({POLICY_USING_EXPR})"
    )

    # --- seed defaults for existing departments ---------------------------
    bind = op.get_bind()

    depts = bind.execute(
        sa.text(
            """
            SELECT id, business_id, template_key
            FROM departments
            WHERE template_key IS NOT NULL
            """
        )
    ).mappings().all()

    slot_inserts: list[dict[str, Any]] = []
    handoff_inserts: list[dict[str, Any]] = []

    for dept in depts:
        template_key = dept["template_key"]
        # Slot mappings — only insert when a role with the default key
        # actually exists in this department; the UI fixes any gaps.
        role_keys = DEFAULT_SLOT_ROLE_KEYS.get(template_key, {})
        if role_keys:
            existing_roles = bind.execute(
                sa.text(
                    """
                    SELECT id, key FROM department_roles
                    WHERE department_id = :dept_id
                    """
                ),
                {"dept_id": str(dept["id"])},
            ).mappings().all()
            role_id_by_key = {r["key"]: r["id"] for r in existing_roles}
            for slot_key, role_key in role_keys.items():
                role_id = role_id_by_key.get(role_key)
                if role_id is None:
                    continue
                slot_inserts.append(
                    {
                        "business_id": str(dept["business_id"]),
                        "department_id": str(dept["id"]),
                        "slot_key": slot_key,
                        "department_role_id": str(role_id),
                    }
                )

        # Handoff rules — always seed all template defaults.
        for handoff in DEFAULT_STAGE_HANDOFFS.get(template_key, []):
            handoff_inserts.append(
                {
                    "business_id": str(dept["business_id"]),
                    "department_id": str(dept["id"]),
                    "stage_key": handoff["stage_key"],
                    "slot_keys": handoff["slot_keys"],
                    "removable": handoff["removable"],
                }
            )

    if slot_inserts:
        bind.execute(
            sa.text(
                """
                INSERT INTO department_slot_mappings
                    (id, created_at, updated_at, business_id, department_id,
                     slot_key, department_role_id)
                VALUES
                    (gen_random_uuid(), now(), now(), :business_id, :department_id,
                     :slot_key, :department_role_id)
                """
            ),
            slot_inserts,
        )

    if handoff_inserts:
        # Bulk insert with JSONB requires type casting in the VALUES.
        for row in handoff_inserts:
            bind.execute(
                sa.text(
                    """
                    INSERT INTO department_stage_handoffs
                        (id, created_at, updated_at, business_id, department_id,
                         stage_key, slot_keys, removable)
                    VALUES
                        (gen_random_uuid(), now(), now(), :business_id, :department_id,
                         :stage_key, CAST(:slot_keys AS jsonb), :removable)
                    """
                ),
                {
                    "business_id": row["business_id"],
                    "department_id": row["department_id"],
                    "stage_key": row["stage_key"],
                    "slot_keys": _json(row["slot_keys"]),
                    "removable": row["removable"],
                },
            )


def _json(value: list[str]) -> str:
    import json
    return json.dumps(value)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON department_stage_handoffs")
    op.execute("ALTER TABLE department_stage_handoffs NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE department_stage_handoffs DISABLE ROW LEVEL SECURITY")
    op.drop_index(
        "ix_department_stage_handoffs_department_id",
        table_name="department_stage_handoffs",
    )
    op.drop_index(
        "ix_department_stage_handoffs_business_id",
        table_name="department_stage_handoffs",
    )
    op.drop_table("department_stage_handoffs")

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON department_slot_mappings")
    op.execute("ALTER TABLE department_slot_mappings NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE department_slot_mappings DISABLE ROW LEVEL SECURITY")
    op.drop_index(
        "ix_department_slot_mappings_department_id",
        table_name="department_slot_mappings",
    )
    op.drop_index(
        "ix_department_slot_mappings_business_id",
        table_name="department_slot_mappings",
    )
    op.drop_table("department_slot_mappings")
