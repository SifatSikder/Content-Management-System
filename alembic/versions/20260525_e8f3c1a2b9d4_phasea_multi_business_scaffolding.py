"""phaseA: multi-business scaffolding (Atlas)

Adds the Business → Department → Workflow data model on top of the existing
real-estate schema without disturbing legacy data.

What changes:
  * 8 new tables: businesses, business_memberships, department_templates,
    departments, department_stages, department_roles,
    department_role_permissions, department_memberships.
  * 3 nullable FK columns on `projects`: business_id, department_id, stage_id
    (backfilled to NOT NULL in Phase B).
  * Denormalised `business_id` column added to every business-scoped child
    table (scripts, script_versions, script_comments, edit_versions,
    edit_comments, locations, location_photos, cast_members, shoots,
    activities, notifications) — keeps RLS policies cheap by avoiding
    recursive joins. Nullable in Phase A; existing rows stay NULL until
    Phase B backfills them.
  * Postgres RLS enabled on every business-scoped table with one shared
    `tenant_isolation` policy:
        USING (business_id = current_setting('app.current_business_id', true)::uuid
               OR current_setting('app.is_super_admin', true) = 'true')
    Phase-A note: NULL business_id rows fall out of the policy. The CEO bit
    `is_super_admin = true` (set by the new BusinessContextMiddleware for
    Role.CEO users) keeps legacy real-estate data visible until Phase B
    backfills.

Revision ID: e8f3c1a2b9d4
Revises: d7b1f2a3c855
Create Date: 2026-05-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e8f3c1a2b9d4"
down_revision: Union[str, Sequence[str], None] = "d7b1f2a3c855"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Tables that get a denormalised business_id column added in this migration.
# Order matters only for downgrade: we drop in reverse creation order.
CHILD_TABLES_NEEDING_BUSINESS_ID = (
    "scripts",
    "script_versions",
    "script_comments",
    "edit_versions",
    "edit_comments",
    "locations",
    "location_photos",
    "cast_members",
    "shoots",
    "activities",
    "notifications",
)

# Every business-scoped table — gets RLS enabled with the shared policy.
RLS_TABLES = (
    "projects",
    "scripts",
    "script_versions",
    "script_comments",
    "edit_versions",
    "edit_comments",
    "activities",
    "locations",
    "location_photos",
    "cast_members",
    "shoots",
    "notifications",
    "departments",
    "department_stages",
    "department_roles",
    "department_role_permissions",
    "department_memberships",
    "business_memberships",
)

POLICY_NAME = "tenant_isolation"
# `NULLIF(...,'')` is load-bearing: Postgres `RESET app.foo` on a custom
# GUC reverts the value to *empty string*, not NULL, so the next request
# (which may reuse the connection from the pool) would otherwise cast `''`
# to uuid and raise `invalid input syntax for type uuid`. NULLIF turns
# unset / reset / empty back into NULL, which is what the comparison
# expects.
POLICY_USING_EXPR = (
    "business_id = NULLIF(current_setting('app.current_business_id', true), '')::uuid "
    "OR current_setting('app.is_super_admin', true) = 'true'"
)


def _enable_rls(table: str) -> None:
    """Enable RLS on `table` and attach the shared tenant_isolation policy."""
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    # Force the policy to also apply to the table owner (otherwise the app
    # role bypasses RLS whenever it owns the table — Postgres default).
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {POLICY_NAME} ON {table} USING ({POLICY_USING_EXPR})"
    )


def _disable_rls(table: str) -> None:
    op.execute(f"DROP POLICY IF EXISTS {POLICY_NAME} ON {table}")
    op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")


def upgrade() -> None:
    # --- 1. Postgres enum for business membership status -------------------
    business_membership_status = postgresql.ENUM(
        "invited",
        "active",
        "revoked",
        name="business_membership_status",
        create_type=True,
    )
    business_membership_status.create(op.get_bind(), checkfirst=True)

    # --- 2. businesses ------------------------------------------------------
    op.create_table(
        "businesses",
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
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("owner_user_id", sa.UUID(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_businesses_slug", "businesses", ["slug"], unique=True)
    op.create_index(
        "ix_businesses_owner_user_id", "businesses", ["owner_user_id"], unique=False
    )
    op.create_index(
        "ix_businesses_deleted_at", "businesses", ["deleted_at"], unique=False
    )

    # --- 3. business_memberships -------------------------------------------
    op.create_table(
        "business_memberships",
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
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(name="business_membership_status", create_type=False),
            nullable=False,
        ),
        sa.Column("invited_by", sa.UUID(), nullable=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "business_id", "user_id", name="uq_business_membership_user"
        ),
    )
    op.create_index(
        "ix_business_memberships_business_id",
        "business_memberships",
        ["business_id"],
        unique=False,
    )
    op.create_index(
        "ix_business_memberships_user_id",
        "business_memberships",
        ["user_id"],
        unique=False,
    )

    # --- 4. department_templates -------------------------------------------
    op.create_table(
        "department_templates",
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
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "default_capabilities",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "default_stages",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "default_roles",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "is_system",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index(
        "ix_department_templates_key", "department_templates", ["key"], unique=True
    )

    # --- 5. departments -----------------------------------------------------
    op.create_table(
        "departments",
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
        sa.Column("template_key", sa.String(length=64), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column(
            "capabilities",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "business_id", "slug", name="uq_department_business_slug"
        ),
    )
    op.create_index(
        "ix_departments_business_id", "departments", ["business_id"], unique=False
    )
    op.create_index(
        "ix_departments_archived_at", "departments", ["archived_at"], unique=False
    )

    # --- 6. department_stages ----------------------------------------------
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
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column(
            "name_i18n",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "is_terminal", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column("color", sa.String(length=32), nullable=True),
        sa.Column(
            "allowed_from_stage_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["department_id"], ["departments.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
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

    # --- 7. department_roles -----------------------------------------------
    op.create_table(
        "department_roles",
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
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column(
            "name_i18n",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["department_id"], ["departments.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("department_id", "key", name="uq_department_role_key"),
    )
    op.create_index(
        "ix_department_roles_department_id",
        "department_roles",
        ["department_id"],
        unique=False,
    )
    op.create_index(
        "ix_department_roles_business_id",
        "department_roles",
        ["business_id"],
        unique=False,
    )

    # --- 8. department_role_permissions ------------------------------------
    op.create_table(
        "department_role_permissions",
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
        sa.Column("department_role_id", sa.UUID(), nullable=False),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("action_key", sa.String(length=128), nullable=False),
        sa.Column("allowed", sa.Boolean(), server_default="false", nullable=False),
        sa.ForeignKeyConstraint(
            ["department_role_id"], ["department_roles.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "department_role_id",
            "action_key",
            name="uq_department_role_permission_action",
        ),
    )
    op.create_index(
        "ix_department_role_permissions_department_role_id",
        "department_role_permissions",
        ["department_role_id"],
        unique=False,
    )
    op.create_index(
        "ix_department_role_permissions_business_id",
        "department_role_permissions",
        ["business_id"],
        unique=False,
    )

    # --- 9. department_memberships -----------------------------------------
    op.create_table(
        "department_memberships",
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
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["department_id"], ["departments.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["role_id"], ["department_roles.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "department_id", "user_id", name="uq_department_membership_user"
        ),
    )
    op.create_index(
        "ix_department_memberships_department_id",
        "department_memberships",
        ["department_id"],
        unique=False,
    )
    op.create_index(
        "ix_department_memberships_business_id",
        "department_memberships",
        ["business_id"],
        unique=False,
    )
    op.create_index(
        "ix_department_memberships_user_id",
        "department_memberships",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_department_memberships_role_id",
        "department_memberships",
        ["role_id"],
        unique=False,
    )

    # --- 10. projects.{business_id, department_id, stage_id} ---------------
    op.add_column(
        "projects",
        sa.Column("business_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("department_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("stage_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_projects_business_id",
        "projects",
        "businesses",
        ["business_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_projects_department_id",
        "projects",
        "departments",
        ["department_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_projects_stage_id",
        "projects",
        "department_stages",
        ["stage_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_projects_business_id", "projects", ["business_id"], unique=False)
    op.create_index(
        "ix_projects_department_id", "projects", ["department_id"], unique=False
    )
    op.create_index("ix_projects_stage_id", "projects", ["stage_id"], unique=False)

    # --- 11. Denormalised business_id on child tables ----------------------
    for table in CHILD_TABLES_NEEDING_BUSINESS_ID:
        op.add_column(
            table,
            sa.Column("business_id", sa.UUID(), nullable=True),
        )
        op.create_foreign_key(
            f"fk_{table}_business_id",
            table,
            "businesses",
            ["business_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        op.create_index(
            f"ix_{table}_business_id", table, ["business_id"], unique=False
        )

    # --- 12. Enable RLS + tenant_isolation policy --------------------------
    for table in RLS_TABLES:
        _enable_rls(table)

    # --- 13. RLS-enforcement role ------------------------------------------
    # The docker image creates `cms_app` as a Postgres superuser via
    # `POSTGRES_USER`, and superusers bypass RLS unconditionally — even
    # with `FORCE ROW LEVEL SECURITY`. We can't strip cms_app's superuser
    # bit (Postgres protects the bootstrap user), so instead we create a
    # second, low-privilege role and have the app `SET LOCAL ROLE` to it
    # at the start of every transaction (see `business_scoped_session`).
    # Inside that transaction RLS enforces; outside it (Alembic, scripts,
    # adhoc psql) cms_app retains superuser for ergonomics.
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'atlas_app') THEN "
        "CREATE ROLE atlas_app NOLOGIN NOSUPERUSER NOBYPASSRLS; "
        "END IF; "
        "END $$;"
    )
    # cms_app needs to be able to `SET ROLE atlas_app`.
    op.execute("GRANT atlas_app TO cms_app")
    # The reduced role needs DML on every existing + future table in
    # `public`. Existing objects get an explicit GRANT; future objects pick
    # up ALTER DEFAULT PRIVILEGES.
    op.execute("GRANT USAGE ON SCHEMA public TO atlas_app")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE "
        "ON ALL TABLES IN SCHEMA public TO atlas_app"
    )
    op.execute(
        "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO atlas_app"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO atlas_app"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT USAGE, SELECT ON SEQUENCES TO atlas_app"
    )


def downgrade() -> None:
    # --- 13. Drop atlas_app role + revoke grants ---------------------------
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM atlas_app"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "REVOKE USAGE, SELECT ON SEQUENCES FROM atlas_app"
    )
    op.execute(
        "REVOKE SELECT, INSERT, UPDATE, DELETE "
        "ON ALL TABLES IN SCHEMA public FROM atlas_app"
    )
    op.execute(
        "REVOKE USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public FROM atlas_app"
    )
    op.execute("REVOKE USAGE ON SCHEMA public FROM atlas_app")
    op.execute("DROP ROLE IF EXISTS atlas_app")

    # --- 12. Drop RLS policies + disable RLS -------------------------------
    for table in RLS_TABLES:
        _disable_rls(table)

    # --- 11. Drop denormalised business_id columns from child tables -------
    for table in reversed(CHILD_TABLES_NEEDING_BUSINESS_ID):
        op.drop_index(f"ix_{table}_business_id", table_name=table)
        op.drop_constraint(f"fk_{table}_business_id", table, type_="foreignkey")
        op.drop_column(table, "business_id")

    # --- 10. Drop projects.{business_id, department_id, stage_id} ----------
    op.drop_index("ix_projects_stage_id", table_name="projects")
    op.drop_index("ix_projects_department_id", table_name="projects")
    op.drop_index("ix_projects_business_id", table_name="projects")
    op.drop_constraint("fk_projects_stage_id", "projects", type_="foreignkey")
    op.drop_constraint("fk_projects_department_id", "projects", type_="foreignkey")
    op.drop_constraint("fk_projects_business_id", "projects", type_="foreignkey")
    op.drop_column("projects", "stage_id")
    op.drop_column("projects", "department_id")
    op.drop_column("projects", "business_id")

    # --- 9. department_memberships -----------------------------------------
    op.drop_index(
        "ix_department_memberships_role_id", table_name="department_memberships"
    )
    op.drop_index(
        "ix_department_memberships_user_id", table_name="department_memberships"
    )
    op.drop_index(
        "ix_department_memberships_business_id", table_name="department_memberships"
    )
    op.drop_index(
        "ix_department_memberships_department_id", table_name="department_memberships"
    )
    op.drop_table("department_memberships")

    # --- 8. department_role_permissions ------------------------------------
    op.drop_index(
        "ix_department_role_permissions_business_id",
        table_name="department_role_permissions",
    )
    op.drop_index(
        "ix_department_role_permissions_department_role_id",
        table_name="department_role_permissions",
    )
    op.drop_table("department_role_permissions")

    # --- 7. department_roles -----------------------------------------------
    op.drop_index("ix_department_roles_business_id", table_name="department_roles")
    op.drop_index("ix_department_roles_department_id", table_name="department_roles")
    op.drop_table("department_roles")

    # --- 6. department_stages ----------------------------------------------
    op.drop_index("ix_department_stages_business_id", table_name="department_stages")
    op.drop_index("ix_department_stages_department_id", table_name="department_stages")
    op.drop_table("department_stages")

    # --- 5. departments -----------------------------------------------------
    op.drop_index("ix_departments_archived_at", table_name="departments")
    op.drop_index("ix_departments_business_id", table_name="departments")
    op.drop_table("departments")

    # --- 4. department_templates -------------------------------------------
    op.drop_index("ix_department_templates_key", table_name="department_templates")
    op.drop_table("department_templates")

    # --- 3. business_memberships -------------------------------------------
    op.drop_index(
        "ix_business_memberships_user_id", table_name="business_memberships"
    )
    op.drop_index(
        "ix_business_memberships_business_id", table_name="business_memberships"
    )
    op.drop_table("business_memberships")

    # --- 2. businesses ------------------------------------------------------
    op.drop_index("ix_businesses_deleted_at", table_name="businesses")
    op.drop_index("ix_businesses_owner_user_id", table_name="businesses")
    op.drop_index("ix_businesses_slug", table_name="businesses")
    op.drop_table("businesses")

    # --- 1. Drop business_membership_status enum ---------------------------
    postgresql.ENUM(name="business_membership_status").drop(
        op.get_bind(), checkfirst=True
    )
