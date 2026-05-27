"""Mirror the idea signoff loop onto scripts.

Revision ID: f4a92c8b1d57
Revises: e8b1c4f72d35
Create Date: 2026-05-27 23:00:00.000000

Adds `script_signoffs` (one row per (version, reviewer)) and the
`script_signoff_decision` Postgres enum. RLS via shared
`tenant_isolation` policy. Mirrors idea_signoffs.

The script + script_versions tables already exist with `submitted_at`
on versions, so no new columns on those.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f4a92c8b1d57"
down_revision: Union[str, Sequence[str], None] = "e8b1c4f72d35"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


POLICY_NAME = "tenant_isolation"
POLICY_USING_EXPR = (
    "business_id = NULLIF(current_setting('app.current_business_id', true), '')::uuid "
    "OR current_setting('app.is_super_admin', true) = 'true'"
)


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {POLICY_NAME} ON {table} USING ({POLICY_USING_EXPR})"
    )


def _disable_rls(table: str) -> None:
    op.execute(f"DROP POLICY IF EXISTS {POLICY_NAME} ON {table}")
    op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")


def upgrade() -> None:
    decision_enum = postgresql.ENUM(
        "looks_good",
        "needs_changes",
        name="script_signoff_decision",
        create_type=True,
    )
    decision_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "script_signoffs",
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
        sa.Column("script_version_id", sa.UUID(), nullable=False),
        sa.Column("reviewer_id", sa.UUID(), nullable=False),
        sa.Column(
            "decision",
            postgresql.ENUM(name="script_signoff_decision", create_type=False),
            nullable=False,
        ),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["script_version_id"], ["script_versions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_script_signoffs_business_id", "script_signoffs", ["business_id"]
    )
    op.create_index(
        "ix_script_signoffs_version", "script_signoffs", ["script_version_id"]
    )
    op.create_index(
        "ix_script_signoffs_reviewer", "script_signoffs", ["reviewer_id"]
    )
    _enable_rls("script_signoffs")


def downgrade() -> None:
    _disable_rls("script_signoffs")
    op.drop_index("ix_script_signoffs_reviewer", table_name="script_signoffs")
    op.drop_index("ix_script_signoffs_version", table_name="script_signoffs")
    op.drop_index("ix_script_signoffs_business_id", table_name="script_signoffs")
    op.drop_table("script_signoffs")
    postgresql.ENUM(name="script_signoff_decision").drop(
        op.get_bind(), checkfirst=True
    )
