"""Phase 5 of board-flow rework: draft-idea versioning + signoffs.

Revision ID: c3b770e19451
Revises: 863ba5cb3f3a
Create Date: 2026-05-27 16:00:00.000000

Three new business-scoped tables (all RLS via shared `tenant_isolation`):

  ideas             — one per project; carries the per-project lock
                      state for the draft-idea phase.
  idea_versions     — immutable snapshots of the idea body. Bumped on save.
  idea_signoffs     — per-(version, reviewer) decision. Latest row per
                      reviewer is authoritative.

Plus a Postgres ENUM `idea_signoff_decision` (looks_good | needs_changes).

No data backfill — projects on `draft_idea` today (none in dev) will
simply have no idea row until the Asst CEO creates V1.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c3b770e19451"
down_revision: Union[str, Sequence[str], None] = "863ba5cb3f3a"
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
    # Enum first — referenced by idea_signoffs.decision.
    decision_enum = postgresql.ENUM(
        "looks_good",
        "needs_changes",
        name="idea_signoff_decision",
        create_type=True,
    )
    decision_enum.create(op.get_bind(), checkfirst=True)

    # ---- ideas ----------------------------------------------------------
    op.create_table(
        "ideas",
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
        sa.Column("current_version_id", sa.UUID(), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["locked_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", name="uq_ideas_project_id"),
    )
    op.create_index("ix_ideas_business_id", "ideas", ["business_id"])
    _enable_rls("ideas")

    # ---- idea_versions --------------------------------------------------
    op.create_table(
        "idea_versions",
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
        sa.Column("idea_id", sa.UUID(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("body_markdown", sa.Text(), nullable=False),
        sa.Column("author_id", sa.UUID(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["idea_id"], ["ideas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idea_id", "version_number", name="uq_idea_version_number"),
    )
    op.create_index("ix_idea_versions_business_id", "idea_versions", ["business_id"])
    op.create_index("ix_idea_versions_idea_id", "idea_versions", ["idea_id"])
    _enable_rls("idea_versions")

    # The `current_version_id` FK on ideas could only be added now that
    # idea_versions exists. Use ALTER to add it post-hoc.
    op.create_foreign_key(
        "fk_ideas_current_version_id",
        "ideas",
        "idea_versions",
        ["current_version_id"],
        ["id"],
        ondelete="SET NULL",
        use_alter=True,
    )

    # ---- idea_signoffs --------------------------------------------------
    op.create_table(
        "idea_signoffs",
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
        sa.Column("idea_version_id", sa.UUID(), nullable=False),
        sa.Column("reviewer_id", sa.UUID(), nullable=False),
        sa.Column(
            "decision",
            postgresql.ENUM(name="idea_signoff_decision", create_type=False),
            nullable=False,
        ),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["idea_version_id"], ["idea_versions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_idea_signoffs_business_id", "idea_signoffs", ["business_id"])
    op.create_index("ix_idea_signoffs_version", "idea_signoffs", ["idea_version_id"])
    op.create_index("ix_idea_signoffs_reviewer", "idea_signoffs", ["reviewer_id"])
    _enable_rls("idea_signoffs")


def downgrade() -> None:
    _disable_rls("idea_signoffs")
    op.drop_index("ix_idea_signoffs_reviewer", table_name="idea_signoffs")
    op.drop_index("ix_idea_signoffs_version", table_name="idea_signoffs")
    op.drop_index("ix_idea_signoffs_business_id", table_name="idea_signoffs")
    op.drop_table("idea_signoffs")

    op.drop_constraint("fk_ideas_current_version_id", "ideas", type_="foreignkey")

    _disable_rls("idea_versions")
    op.drop_index("ix_idea_versions_idea_id", table_name="idea_versions")
    op.drop_index("ix_idea_versions_business_id", table_name="idea_versions")
    op.drop_table("idea_versions")

    _disable_rls("ideas")
    op.drop_index("ix_ideas_business_id", table_name="ideas")
    op.drop_table("ideas")

    postgresql.ENUM(name="idea_signoff_decision").drop(op.get_bind(), checkfirst=True)
