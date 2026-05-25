"""phaseC: Marketing template + rename cast_members → participants + capability
config + terminology overrides.

What this migration does (single transaction):

  1. Renames `cast_members` → `participants`. Drops the RLS policy on the
     old name and recreates it on the new one. The denormalised
     `business_id` column from Phase A comes along for the ride.
  2. Adds `participants.kind` (default `'cast'`) + nullable lead-only columns
     (`source`, `notes`).
  3. Adds `department_templates.default_capability_configs` JSONB +
     `default_terminology` JSONB.
  4. Adds `departments.capability_configs` JSONB + `terminology` JSONB.
  5. Upserts the Marketing template + refreshes the Content Creation
     template so both have capability_configs + terminology populated.
  6. Backfills the existing Sons Real Estate / Content Creation department
     row with the new fields.

Revision ID: d5e8f2a9c1b6
Revises: c4d7e2a1f8b3
Create Date: 2026-05-25
"""
from __future__ import annotations

import json
from typing import Any, Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

from app.seeds.templates import all_templates

revision: str = "d5e8f2a9c1b6"
down_revision: Union[str, Sequence[str], None] = "c4d7e2a1f8b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


POLICY_NAME = "tenant_isolation"
POLICY_USING_EXPR = (
    "business_id = NULLIF(current_setting('app.current_business_id', true), '')::uuid "
    "OR current_setting('app.is_super_admin', true) = 'true'"
)


def upgrade() -> None:
    bind = op.get_bind()

    # --- 1. Rename cast_members → participants ----------------------------
    # Drop the RLS policy on the old name first; CREATE POLICY pins to the
    # table id, not the name, so the rename would otherwise carry an orphaned
    # policy reference. Index/FK names get renamed to keep things tidy.
    op.execute(f"DROP POLICY IF EXISTS {POLICY_NAME} ON cast_members")
    op.rename_table("cast_members", "participants")

    # Indexes from Phase A migration: `ix_cast_members_business_id`. Rename to
    # the new convention so downgrade can find them again.
    op.execute(
        "ALTER INDEX IF EXISTS ix_cast_members_business_id "
        "RENAME TO ix_participants_business_id"
    )
    # Phase A's denormalised FK constraint name.
    op.execute(
        "ALTER TABLE participants RENAME CONSTRAINT fk_cast_members_business_id "
        "TO fk_participants_business_id"
    )

    # Re-enable RLS on the renamed table with the shared policy.
    op.execute("ALTER TABLE participants ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE participants FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {POLICY_NAME} ON participants USING ({POLICY_USING_EXPR})"
    )

    # --- 2. Discriminator + lead-only columns -----------------------------
    op.add_column(
        "participants",
        sa.Column(
            "kind",
            sa.String(length=16),
            server_default="cast",
            nullable=False,
        ),
    )
    op.add_column("participants", sa.Column("source", sa.String(length=120), nullable=True))
    op.add_column("participants", sa.Column("notes", sa.Text(), nullable=True))

    # --- 3. department_templates.{default_capability_configs, default_terminology}
    op.add_column(
        "department_templates",
        sa.Column(
            "default_capability_configs",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
    )
    op.add_column(
        "department_templates",
        sa.Column(
            "default_terminology",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
    )

    # --- 4. departments.{capability_configs, terminology} -----------------
    op.add_column(
        "departments",
        sa.Column(
            "capability_configs",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
    )
    op.add_column(
        "departments",
        sa.Column(
            "terminology",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
    )

    # --- 5. Upsert every registered template (Content Creation refreshed,
    #         Marketing seeded for the first time). The data migration in
    #         Phase B used this same shape; Phase C extends it with the new
    #         JSONB columns.
    for tpl in all_templates():
        bind.execute(
            text(
                """
                INSERT INTO department_templates (
                    id, key, name, description,
                    default_capabilities, default_stages, default_roles,
                    default_capability_configs, default_terminology,
                    is_system
                )
                VALUES (
                    gen_random_uuid(), :key, :name, :description,
                    CAST(:default_capabilities AS JSONB),
                    CAST(:default_stages AS JSONB),
                    CAST(:default_roles AS JSONB),
                    CAST(:default_capability_configs AS JSONB),
                    CAST(:default_terminology AS JSONB),
                    :is_system
                )
                ON CONFLICT (key) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    default_capabilities = EXCLUDED.default_capabilities,
                    default_stages = EXCLUDED.default_stages,
                    default_roles = EXCLUDED.default_roles,
                    default_capability_configs = EXCLUDED.default_capability_configs,
                    default_terminology = EXCLUDED.default_terminology,
                    is_system = EXCLUDED.is_system,
                    updated_at = now()
                """
            ),
            {
                "key": tpl["key"],
                "name": tpl["name"],
                "description": tpl.get("description"),
                "default_capabilities": json.dumps(tpl.get("default_capabilities", [])),
                "default_stages": json.dumps(tpl.get("default_stages", [])),
                "default_roles": json.dumps(tpl.get("default_roles", [])),
                "default_capability_configs": json.dumps(
                    tpl.get("default_capability_configs", {})
                ),
                "default_terminology": json.dumps(tpl.get("default_terminology", {})),
                "is_system": bool(tpl.get("is_system", False)),
            },
        )

    # --- 6. Backfill existing Content Creation department rows -----------
    # Live departments instantiated *before* this migration carry empty JSONB
    # on the two new columns. For the seeded "Sons Real Estate / Content
    # Creation" department we mirror the template's defaults so the kanban
    # + project pages get the right config without forcing a re-instantiation.
    content_creation = next(
        (t for t in all_templates() if t["key"] == "content_creation"), None
    )
    if content_creation is not None:
        bind.execute(
            text(
                """
                UPDATE departments
                   SET capability_configs = CAST(:configs AS JSONB),
                       terminology        = CAST(:terminology AS JSONB),
                       updated_at         = now()
                  WHERE template_key = 'content_creation'
                    AND (capability_configs = '{}'::jsonb OR terminology = '{}'::jsonb)
                """
            ),
            {
                "configs": json.dumps(
                    content_creation.get("default_capability_configs", {})
                ),
                "terminology": json.dumps(content_creation.get("default_terminology", {})),
            },
        )


def downgrade() -> None:
    bind = op.get_bind()

    # --- 6/5. Pull the Marketing template seed back out -------------------
    bind.execute(
        text("DELETE FROM department_templates WHERE key = 'marketing'")
    )

    # --- 4. Drop departments columns -------------------------------------
    op.drop_column("departments", "terminology")
    op.drop_column("departments", "capability_configs")

    # --- 3. Drop department_templates columns ----------------------------
    op.drop_column("department_templates", "default_terminology")
    op.drop_column("department_templates", "default_capability_configs")

    # --- 2. Drop participant lead-only columns + kind --------------------
    op.drop_column("participants", "notes")
    op.drop_column("participants", "source")
    op.drop_column("participants", "kind")

    # --- 1. Rename participants → cast_members ---------------------------
    op.execute(f"DROP POLICY IF EXISTS {POLICY_NAME} ON participants")
    op.execute(
        "ALTER TABLE participants RENAME CONSTRAINT fk_participants_business_id "
        "TO fk_cast_members_business_id"
    )
    op.execute(
        "ALTER INDEX IF EXISTS ix_participants_business_id "
        "RENAME TO ix_cast_members_business_id"
    )
    op.rename_table("participants", "cast_members")
    op.execute("ALTER TABLE cast_members ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE cast_members FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {POLICY_NAME} ON cast_members USING ({POLICY_USING_EXPR})"
    )


# Re-export so `op.get_bind()` returns Any without mypy complaining about
# uninferable types in the dict literals above.
_ = Any
