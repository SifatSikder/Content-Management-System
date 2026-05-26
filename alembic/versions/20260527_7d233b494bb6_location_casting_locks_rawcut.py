"""Phase 3 of board-flow rework: location/casting lock columns + raw_cut_submissions.

Revision ID: 7d233b494bb6
Revises: 552b325ccb2f
Create Date: 2026-05-27 14:00:00.000000

- Adds `projects.location_locked_at/by`, `projects.casting_locked_at/by`
  (nullable) — locking is a project property like the existing script lock.
- Creates the `raw_cut_submissions` table (business-scoped, RLS) for the
  director's end-of-shoot file uploads.
- Seeds the new permission `action_key`s (`location.lock`, `casting.lock`,
  `raw_cut.submit`) onto existing Content Creation department roles
  matching the template defaults — `ceo` and `assistant_director` get all
  three; `junior_director` only gets `raw_cut.submit`.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "7d233b494bb6"
down_revision: Union[str, Sequence[str], None] = "552b325ccb2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


POLICY_NAME = "tenant_isolation"
POLICY_USING_EXPR = (
    "business_id = NULLIF(current_setting('app.current_business_id', true), '')::uuid "
    "OR current_setting('app.is_super_admin', true) = 'true'"
)

ROLE_ACTIONS: dict[str, list[str]] = {
    "ceo": ["location.lock", "casting.lock", "raw_cut.submit"],
    "assistant_director": ["location.lock", "casting.lock", "raw_cut.submit"],
    "junior_director": ["raw_cut.submit"],
}


def upgrade() -> None:
    # --- 1. projects lock columns ----------------------------------------
    op.add_column(
        "projects",
        sa.Column("location_locked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("location_locked_by", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_projects_location_locked_by",
        "projects",
        "users",
        ["location_locked_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "projects",
        sa.Column("casting_locked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("casting_locked_by", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_projects_casting_locked_by",
        "projects",
        "users",
        ["casting_locked_by"],
        ["id"],
        ondelete="SET NULL",
    )

    # --- 2. raw_cut_submissions table -----------------------------------
    op.create_table(
        "raw_cut_submissions",
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
        sa.Column("uploader_id", sa.UUID(), nullable=False),
        sa.Column("gcs_bucket", sa.String(length=128), nullable=False),
        sa.Column("gcs_object_name", sa.String(length=512), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("content_type", sa.String(length=120), nullable=True),
        sa.Column("byte_size", sa.BigInteger(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploader_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_raw_cut_submissions_business_id",
        "raw_cut_submissions",
        ["business_id"],
    )
    op.create_index(
        "ix_raw_cut_submissions_project_id",
        "raw_cut_submissions",
        ["project_id"],
    )

    # RLS for raw_cut_submissions
    op.execute("ALTER TABLE raw_cut_submissions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE raw_cut_submissions FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {POLICY_NAME} ON raw_cut_submissions "
        f"USING ({POLICY_USING_EXPR})"
    )

    # --- 3. seed new permission action_keys on existing CC dept roles ---
    bind = op.get_bind()
    roles = bind.execute(
        sa.text(
            """
            SELECT r.id AS role_id,
                   r.business_id AS business_id,
                   r.key AS role_key
            FROM department_roles r
            JOIN departments d ON d.id = r.department_id
            WHERE d.template_key = 'content_creation'
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
                WHERE action_key IN ('location.lock', 'casting.lock', 'raw_cut.submit')
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
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            DELETE FROM department_role_permissions
            WHERE action_key IN ('location.lock', 'casting.lock', 'raw_cut.submit')
            """
        )
    )

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON raw_cut_submissions")
    op.execute("ALTER TABLE raw_cut_submissions NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE raw_cut_submissions DISABLE ROW LEVEL SECURITY")
    op.drop_index(
        "ix_raw_cut_submissions_project_id", table_name="raw_cut_submissions"
    )
    op.drop_index(
        "ix_raw_cut_submissions_business_id", table_name="raw_cut_submissions"
    )
    op.drop_table("raw_cut_submissions")

    op.drop_constraint(
        "fk_projects_casting_locked_by", "projects", type_="foreignkey"
    )
    op.drop_column("projects", "casting_locked_by")
    op.drop_column("projects", "casting_locked_at")
    op.drop_constraint(
        "fk_projects_location_locked_by", "projects", type_="foreignkey"
    )
    op.drop_column("projects", "location_locked_by")
    op.drop_column("projects", "location_locked_at")
