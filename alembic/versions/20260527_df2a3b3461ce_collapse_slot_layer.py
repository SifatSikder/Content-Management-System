"""Collapse the slot layer — stage handoffs reference roles directly.

Revision ID: df2a3b3461ce
Revises: c3b770e19451
Create Date: 2026-05-27 17:00:00.000000

Replaces the two-step slot abstraction with a single direct mapping:

  department_stage_handoffs.slot_keys (jsonb[str])
    becomes
  department_stage_handoffs.role_ids (jsonb[uuid])

`department_slot_mappings` is dropped wholesale; its only purpose was to
translate slot keys to role ids, and the new column does that translation
once at write-time instead of at every read.

`project_stage_assignments.slot_key` is dropped — without slots there's
no useful "seeded vs manual" identifier on the row.

Data migration:
  - For each existing handoff row, resolve each slot_key to the role_id
    via the existing slot_mappings table; the new role_ids array is the
    de-duplicated set of resolved ids. Unmapped slots are silently
    dropped (matches their current runtime behaviour anyway).
"""

from __future__ import annotations

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "df2a3b3461ce"
down_revision: Union[str, Sequence[str], None] = "c3b770e19451"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Add the new role_ids column (nullable for the backfill window).
    op.add_column(
        "department_stage_handoffs",
        sa.Column(
            "role_ids",
            sa.dialects.postgresql.JSONB(),
            nullable=True,
        ),
    )

    # 2. Backfill role_ids from slot_keys via slot_mappings join.
    handoffs = bind.execute(
        sa.text(
            """
            SELECT id, department_id, slot_keys
            FROM department_stage_handoffs
            """
        )
    ).mappings().all()
    for row in handoffs:
        slot_keys = row["slot_keys"] or []
        if not slot_keys:
            bind.execute(
                sa.text(
                    "UPDATE department_stage_handoffs SET role_ids = CAST(:r AS jsonb) WHERE id = :id"
                ),
                {"r": "[]", "id": str(row["id"])},
            )
            continue
        mappings = bind.execute(
            sa.text(
                """
                SELECT slot_key, department_role_id
                FROM department_slot_mappings
                WHERE department_id = :dept_id
                  AND slot_key = ANY(:keys)
                """
            ),
            {"dept_id": str(row["department_id"]), "keys": list(slot_keys)},
        ).mappings().all()
        seen: set[str] = set()
        ordered: list[str] = []
        # Preserve the original slot order so the UI renders the same sequence.
        slot_to_role = {m["slot_key"]: str(m["department_role_id"]) for m in mappings}
        for slot in slot_keys:
            role_id = slot_to_role.get(slot)
            if role_id and role_id not in seen:
                seen.add(role_id)
                ordered.append(role_id)
        bind.execute(
            sa.text(
                "UPDATE department_stage_handoffs SET role_ids = CAST(:r AS jsonb) WHERE id = :id"
            ),
            {"r": json.dumps(ordered), "id": str(row["id"])},
        )

    # 3. NOT NULL + default for the new column, then drop the old one.
    op.alter_column(
        "department_stage_handoffs",
        "role_ids",
        nullable=False,
        server_default=sa.text("'[]'::jsonb"),
    )
    op.drop_column("department_stage_handoffs", "slot_keys")

    # 4. Drop department_slot_mappings entirely.
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

    # 5. Drop project_stage_assignments.slot_key.
    op.drop_column("project_stage_assignments", "slot_key")


def downgrade() -> None:
    # Restore the slot_key column on project_stage_assignments (data lost).
    op.add_column(
        "project_stage_assignments",
        sa.Column("slot_key", sa.String(length=64), nullable=True),
    )

    # Recreate department_slot_mappings (empty — original mappings lost).
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
        sa.UniqueConstraint("department_id", "slot_key", name="uq_department_slot_mapping"),
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
        "CREATE POLICY tenant_isolation ON department_slot_mappings "
        "USING (business_id = NULLIF(current_setting('app.current_business_id', true), '')::uuid "
        "OR current_setting('app.is_super_admin', true) = 'true')"
    )

    # Restore slot_keys column (empty — role_ids contents not reversible).
    op.add_column(
        "department_stage_handoffs",
        sa.Column(
            "slot_keys",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.drop_column("department_stage_handoffs", "role_ids")
