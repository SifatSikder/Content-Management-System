"""Phase 2 of board-flow rework: project_stage_assignments table.

Revision ID: 552b325ccb2f
Revises: 2a5d57922e06
Create Date: 2026-05-27 12:30:00.000000

Introduce per-stage, multi-assignee, history-preserving assignment of users
to projects. Active assignees on a card = `removed_at IS NULL`. Backfills
one row per existing project: `(stage_key=project.stage_key,
user_id=project.owner_id, assigned_at=now())`.

RLS uses the shared `tenant_isolation` policy via the table's own
`business_id` column (same pattern as scripts / edits / locations).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "552b325ccb2f"
down_revision: Union[str, Sequence[str], None] = "2a5d57922e06"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


POLICY_NAME = "tenant_isolation"
POLICY_USING_EXPR = (
    "business_id = NULLIF(current_setting('app.current_business_id', true), '')::uuid "
    "OR current_setting('app.is_super_admin', true) = 'true'"
)


def upgrade() -> None:
    op.create_table(
        "project_stage_assignments",
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
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("stage_key", sa.String(length=120), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("slot_key", sa.String(length=64), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assigned_by", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assigned_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_project_stage_assignments_business_id",
        "project_stage_assignments",
        ["business_id"],
    )
    op.create_index(
        "ix_project_stage_assignments_project_id",
        "project_stage_assignments",
        ["project_id"],
    )
    op.create_index(
        "ix_project_stage_assignments_user_id",
        "project_stage_assignments",
        ["user_id"],
    )
    op.create_index(
        "ix_project_stage_assignments_project_stage_active",
        "project_stage_assignments",
        ["project_id", "stage_key", "removed_at"],
    )

    # RLS
    op.execute(
        "ALTER TABLE project_stage_assignments ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE project_stage_assignments FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        f"CREATE POLICY {POLICY_NAME} ON project_stage_assignments "
        f"USING ({POLICY_USING_EXPR})"
    )

    # Backfill: one assignment per existing project, anchored at the
    # project's current stage and assigned to the owner.
    op.execute(
        """
        INSERT INTO project_stage_assignments (
            id, created_at, updated_at, business_id, project_id, stage_key,
            user_id, slot_key, assigned_at, removed_at, assigned_by
        )
        SELECT
            gen_random_uuid(), now(), now(), p.business_id, p.id,
            p.stage_key, p.owner_id, NULL, now(), NULL, NULL
        FROM projects p
        WHERE p.deleted_at IS NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON project_stage_assignments")
    op.execute("ALTER TABLE project_stage_assignments NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE project_stage_assignments DISABLE ROW LEVEL SECURITY")
    op.drop_index(
        "ix_project_stage_assignments_project_stage_active",
        table_name="project_stage_assignments",
    )
    op.drop_index(
        "ix_project_stage_assignments_user_id",
        table_name="project_stage_assignments",
    )
    op.drop_index(
        "ix_project_stage_assignments_project_id",
        table_name="project_stage_assignments",
    )
    op.drop_index(
        "ix_project_stage_assignments_business_id",
        table_name="project_stage_assignments",
    )
    op.drop_table("project_stage_assignments")
