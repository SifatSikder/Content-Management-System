"""Per-(version, reviewer) edit approval rows.

Revision ID: d8f4e2a1b95c
Revises: a93f7d5c2e8b
Create Date: 2026-05-28 04:00:00.000000

Replaces the single-flip `approve_edit` model: both CEO and Asst CEO
must independently sign off on the editor's current cut before the
project can advance to `approved_published`. Each approval is one row
in `edit_approvals`. `EditVersionModel.approved_at/by` stays on the
table (now stamped to the last reviewer who completed the gate).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d8f4e2a1b95c"
down_revision: Union[str, Sequence[str], None] = "a93f7d5c2e8b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


POLICY_NAME = "tenant_isolation"
POLICY_USING_EXPR = (
    "business_id = NULLIF(current_setting('app.current_business_id', true), '')::uuid "
    "OR current_setting('app.is_super_admin', true) = 'true'"
)


def upgrade() -> None:
    op.create_table(
        "edit_approvals",
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
        sa.Column("edit_version_id", sa.UUID(), nullable=False),
        sa.Column("reviewer_id", sa.UUID(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["edit_version_id"], ["edit_versions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "edit_version_id", "reviewer_id", name="uq_edit_approval_reviewer"
        ),
    )
    op.create_index(
        "ix_edit_approvals_business_id", "edit_approvals", ["business_id"]
    )
    op.create_index(
        "ix_edit_approvals_version", "edit_approvals", ["edit_version_id"]
    )
    op.create_index(
        "ix_edit_approvals_reviewer", "edit_approvals", ["reviewer_id"]
    )
    op.execute("ALTER TABLE edit_approvals ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE edit_approvals FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {POLICY_NAME} ON edit_approvals USING ({POLICY_USING_EXPR})"
    )


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS {POLICY_NAME} ON edit_approvals")
    op.execute("ALTER TABLE edit_approvals NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE edit_approvals DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_edit_approvals_reviewer", table_name="edit_approvals")
    op.drop_index("ix_edit_approvals_version", table_name="edit_approvals")
    op.drop_index("ix_edit_approvals_business_id", table_name="edit_approvals")
    op.drop_table("edit_approvals")
