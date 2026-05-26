"""drop department_stages table; projects switch to stage_key string

Revision ID: a1b9d3e7c5f2
Revises: abe94244ee2f
Create Date: 2026-05-26 17:00:00.000000

Partial reversal of Phase B's stages-in-DB decision. Stages return to
code-only constants per template (see `app/services/stage_registry.py` and
`app/seeds/templates/<key>.py::STAGES`). The DB only needs to remember
*which* stage each project sits on, so `projects.stage_id (FK)` becomes
`projects.stage_key (text)`.

Order:
  1. Add nullable `projects.stage_key`.
  2. Backfill from JOIN `department_stages.key`.
  3. NOT NULL + index.
  4. Drop FK `fk_projects_stage_id`, drop index `ix_projects_stage_id`,
     drop `stage_id` column.
  5. Drop RLS policy + force-RLS on `department_stages`, drop the table
     and its indexes.

Downgrade rebuilds `department_stages` from the in-code `STAGES` registry,
recreates `projects.stage_id` populated by matching `(template_key,
stage_key)` back to the recreated rows, then drops `stage_key`.
"""

from __future__ import annotations

import json
from typing import Any, Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b9d3e7c5f2"
down_revision: Union[str, Sequence[str], None] = "abe94244ee2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add nullable `stage_key`.
    op.add_column(
        "projects",
        sa.Column("stage_key", sa.String(length=120), nullable=True),
    )

    # 2. Backfill.
    op.execute(
        """
        UPDATE projects p
        SET stage_key = ds.key
        FROM department_stages ds
        WHERE p.stage_id = ds.id
        """
    )

    # 3. NOT NULL + index.
    op.alter_column("projects", "stage_key", nullable=False)
    op.create_index("ix_projects_stage_key", "projects", ["stage_key"], unique=False)

    # 4. Drop FK + index + column on stage_id.
    op.drop_constraint("fk_projects_stage_id", "projects", type_="foreignkey")
    op.drop_index("ix_projects_stage_id", table_name="projects")
    op.drop_column("projects", "stage_id")

    # 5. Drop RLS policy, force-RLS, and table.
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON department_stages")
    op.execute("ALTER TABLE department_stages NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE department_stages DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_department_stages_business_id", table_name="department_stages")
    op.drop_index("ix_department_stages_department_id", table_name="department_stages")
    op.drop_table("department_stages")


def downgrade() -> None:
    # Recreate the table (mirrors the original Phase A shape).
    op.create_table(
        "department_stages",
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
        sa.Column("department_id", sa.UUID(), nullable=False),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("name_i18n", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("is_terminal", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("color", sa.String(length=32), nullable=True),
        sa.Column(
            "allowed_from_stage_ids",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.ForeignKeyConstraint(
            ["department_id"], ["departments.id"], ondelete="CASCADE", name="fk_department_stages_department_id"
        ),
        sa.ForeignKeyConstraint(
            ["business_id"], ["businesses.id"], ondelete="CASCADE", name="fk_department_stages_business_id"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("department_id", "key", name="uq_department_stage_key"),
    )
    op.create_index(
        "ix_department_stages_department_id",
        "department_stages",
        ["department_id"],
        unique=False,
    )
    op.create_index(
        "ix_department_stages_business_id",
        "department_stages",
        ["business_id"],
        unique=False,
    )
    op.execute("ALTER TABLE department_stages ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE department_stages FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON department_stages USING ("
        "business_id = NULLIF(current_setting('app.current_business_id', true), '')::uuid "
        "OR current_setting('app.is_super_admin', true) = 'true')"
    )

    # Re-seed stages from the in-code STAGES registry, one department at a
    # time, using each department's template_key.
    from app.seeds.templates import content_creation, marketing

    stages_by_template: dict[str, list[dict[str, Any]]] = {
        content_creation.TEMPLATE["key"]: content_creation.STAGES,
        marketing.TEMPLATE["key"]: marketing.STAGES,
    }

    bind = op.get_bind()
    departments = bind.execute(
        sa.text("SELECT id, business_id, template_key FROM departments")
    ).fetchall()

    for dep_id, biz_id, template_key in departments:
        seeds = stages_by_template.get(template_key, [])
        if not seeds:
            continue
        # First pass: insert rows, capture id-by-key for the cross-reference
        # resolution that follows.
        key_to_id: dict[str, str] = {}
        for idx, spec in enumerate(seeds):
            result = bind.execute(
                sa.text(
                    """
                    INSERT INTO department_stages (
                        id, department_id, business_id, key, name_i18n,
                        order_index, is_terminal, color, allowed_from_stage_ids
                    )
                    VALUES (
                        gen_random_uuid(), :dep_id, :biz_id, :key,
                        CAST(:name_i18n AS JSONB), :order_index, :is_terminal,
                        :color, CAST('[]' AS JSONB)
                    )
                    RETURNING id
                    """
                ),
                {
                    "dep_id": dep_id,
                    "biz_id": biz_id,
                    "key": spec["key"],
                    "name_i18n": json.dumps(spec.get("name_i18n", {})),
                    "order_index": spec.get("order_index", idx),
                    "is_terminal": bool(spec.get("is_terminal", False)),
                    "color": spec.get("color"),
                },
            )
            row = result.fetchone()
            if row is not None:
                key_to_id[spec["key"]] = str(row[0])

        # Second pass: backfill allowed_from_stage_ids using the keys.
        for spec in seeds:
            allowed_keys = spec.get("allowed_from_stage_keys", []) or []
            ids = [key_to_id[k] for k in allowed_keys if k in key_to_id]
            if not ids:
                continue
            bind.execute(
                sa.text(
                    """
                    UPDATE department_stages
                    SET allowed_from_stage_ids = CAST(:ids AS JSONB)
                    WHERE department_id = :dep_id AND key = :key
                    """
                ),
                {
                    "dep_id": dep_id,
                    "key": spec["key"],
                    "ids": json.dumps(ids),
                },
            )

    # Recreate projects.stage_id, backfilled by matching template_key + key.
    op.add_column("projects", sa.Column("stage_id", sa.UUID(), nullable=True))
    op.execute(
        """
        UPDATE projects p
        SET stage_id = ds.id
        FROM department_stages ds, departments d
        WHERE p.department_id = d.id
          AND ds.department_id = d.id
          AND ds.key = p.stage_key
        """
    )
    op.alter_column("projects", "stage_id", nullable=False)
    op.create_index("ix_projects_stage_id", "projects", ["stage_id"], unique=False)
    op.create_foreign_key(
        "fk_projects_stage_id",
        "projects",
        "department_stages",
        ["stage_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.drop_index("ix_projects_stage_key", table_name="projects")
    op.drop_column("projects", "stage_key")
