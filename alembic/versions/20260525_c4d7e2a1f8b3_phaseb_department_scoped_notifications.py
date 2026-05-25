"""phaseB: department-scoped notification events.

Replaces the 9-column wide `user_notification_prefs.push_*` schema with two
new tables:

  * `department_event_definitions`  — (department_id, event_key) → name + default
  * `user_notification_pref_events` — (user_id, department_id, event_key) → enabled

Seeds the 9 legacy event keys into Content Creation's department, then
migrates each existing `user_notification_prefs` row's nine booleans into
`user_notification_pref_events` rows for the Content Creation department.
The `user_notification_prefs` table itself stays — its `id`/`user_id` row
is harmless and might be useful for future cross-department defaults —
but the per-event columns are dropped.

Revision ID: c4d7e2a1f8b3
Revises: b3f8c5d1a7e9
Create Date: 2026-05-25
"""
from __future__ import annotations

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c4d7e2a1f8b3"
down_revision: Union[str, Sequence[str], None] = "b3f8c5d1a7e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


POLICY_NAME = "tenant_isolation"
POLICY_USING_EXPR = (
    "business_id = NULLIF(current_setting('app.current_business_id', true), '')::uuid "
    "OR current_setting('app.is_super_admin', true) = 'true'"
)


# (event_key, default_enabled, name_en, name_nl)
LEGACY_EVENTS: list[tuple[str, bool, str, str]] = [
    ("project_created", True, "New project created", "Nieuw project aangemaakt"),
    ("script_submitted", True, "Script submitted for review", "Script ingediend voor review"),
    ("script_locked", True, "Script locked", "Script vergrendeld"),
    ("cut_uploaded", True, "New cut uploaded", "Nieuwe montage geüpload"),
    ("cut_comment", True, "Comment on a cut", "Reactie op een montage"),
    ("cut_approved", True, "Cut approved", "Montage goedgekeurd"),
    ("cut_changes_requested", True, "Changes requested on a cut", "Wijzigingen gevraagd op een montage"),
    ("project_published", True, "Project published", "Project gepubliceerd"),
    ("project_stuck", True, "Project is stuck", "Project staat stil"),
]


# Column → event_key. Used to migrate existing `user_notification_prefs` rows.
LEGACY_COLUMNS: list[tuple[str, str]] = [
    ("push_project_created", "project_created"),
    ("push_script_submitted", "script_submitted"),
    ("push_script_locked", "script_locked"),
    ("push_cut_uploaded", "cut_uploaded"),
    ("push_cut_comment", "cut_comment"),
    ("push_cut_approved", "cut_approved"),
    ("push_cut_changes_requested", "cut_changes_requested"),
    ("push_project_published", "project_published"),
    ("push_project_stuck", "project_stuck"),
]


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY {POLICY_NAME} ON {table} USING ({POLICY_USING_EXPR})")


def _disable_rls(table: str) -> None:
    op.execute(f"DROP POLICY IF EXISTS {POLICY_NAME} ON {table}")
    op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")


def upgrade() -> None:
    bind = op.get_bind()

    # --- 1. department_event_definitions -----------------------------------
    op.create_table(
        "department_event_definitions",
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
        sa.Column("event_key", sa.String(length=64), nullable=False),
        sa.Column(
            "name_i18n",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "default_enabled",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["department_id"], ["departments.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "department_id", "event_key", name="uq_department_event_key"
        ),
    )
    op.create_index(
        "ix_department_event_definitions_department_id",
        "department_event_definitions",
        ["department_id"],
    )
    op.create_index(
        "ix_department_event_definitions_business_id",
        "department_event_definitions",
        ["business_id"],
    )

    # --- 2. user_notification_pref_events ---------------------------------
    op.create_table(
        "user_notification_pref_events",
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
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("department_id", sa.UUID(), nullable=False),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("event_key", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["department_id"], ["departments.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "department_id",
            "event_key",
            name="uq_user_pref_event",
        ),
    )
    op.create_index(
        "ix_user_notification_pref_events_user_id",
        "user_notification_pref_events",
        ["user_id"],
    )
    op.create_index(
        "ix_user_notification_pref_events_department_id",
        "user_notification_pref_events",
        ["department_id"],
    )
    op.create_index(
        "ix_user_notification_pref_events_business_id",
        "user_notification_pref_events",
        ["business_id"],
    )

    # --- 3. RLS on the new tables -----------------------------------------
    _enable_rls("department_event_definitions")
    _enable_rls("user_notification_pref_events")

    # --- 4. Seed event definitions into Content Creation ------------------
    # Look up the Content Creation department for the Sons Real Estate
    # business (created in Phase B's data migration). If neither exists yet
    # the seed is a no-op — fresh DBs without a CEO user fall into this
    # branch and pick up the events later via `make seed-templates`.
    dept_row = bind.execute(
        sa.text(
            """
            SELECT d.id, d.business_id
              FROM departments d
              JOIN businesses b ON b.id = d.business_id
             WHERE b.slug = 'sons-real-estate'
               AND d.slug = 'content-creation'
             LIMIT 1
            """
        )
    ).first()

    if dept_row is not None:
        dept_id, bid = dept_row
        for event_key, default_enabled, name_en, name_nl in LEGACY_EVENTS:
            bind.execute(
                sa.text(
                    """
                    INSERT INTO department_event_definitions (
                        id, department_id, business_id, event_key, name_i18n,
                        default_enabled
                    )
                    VALUES (
                        gen_random_uuid(), :dept, :bid, :event_key,
                        CAST(:name_i18n AS JSONB), :default_enabled
                    )
                    ON CONFLICT (department_id, event_key) DO UPDATE SET
                        name_i18n = EXCLUDED.name_i18n,
                        default_enabled = EXCLUDED.default_enabled,
                        updated_at = now()
                    """
                ),
                {
                    "dept": dept_id,
                    "bid": bid,
                    "event_key": event_key,
                    "name_i18n": json.dumps({"en": name_en, "nl": name_nl}),
                    "default_enabled": default_enabled,
                },
            )

        # --- 5. Migrate user_notification_prefs.* booleans -------------------
        # Only insert rows that DEVIATE from the column default (true). The
        # absence of a per-event row means "use the department default",
        # which for legacy events is `true` — so unchanged users carry no
        # rows. This keeps the table small while preserving every user's
        # opt-out.
        for column, event_key in LEGACY_COLUMNS:
            bind.execute(
                sa.text(
                    f"""
                    INSERT INTO user_notification_pref_events (
                        id, user_id, department_id, business_id, event_key, enabled
                    )
                    SELECT
                        gen_random_uuid(),
                        unp.user_id,
                        :dept,
                        :bid,
                        :event_key,
                        unp.{column}
                    FROM user_notification_prefs unp
                    WHERE unp.{column} = false
                    ON CONFLICT (user_id, department_id, event_key) DO NOTHING
                    """
                ),
                {"dept": dept_id, "bid": bid, "event_key": event_key},
            )

    # --- 6. Drop the 9 push_* columns from user_notification_prefs -------
    for column, _ in LEGACY_COLUMNS:
        op.drop_column("user_notification_prefs", column)


def downgrade() -> None:
    # --- Restore push_* columns with default=true ----------------------------
    for column, _ in LEGACY_COLUMNS:
        op.add_column(
            "user_notification_prefs",
            sa.Column(
                column,
                sa.Boolean(),
                server_default="true",
                nullable=False,
            ),
        )

    bind = op.get_bind()
    # Restore explicit user opt-outs back onto the wide schema.
    for column, event_key in LEGACY_COLUMNS:
        bind.execute(
            sa.text(
                f"""
                UPDATE user_notification_prefs unp
                   SET {column} = e.enabled
                  FROM user_notification_pref_events e
                 WHERE e.user_id = unp.user_id
                   AND e.event_key = :event_key
                """
            ),
            {"event_key": event_key},
        )

    _disable_rls("user_notification_pref_events")
    _disable_rls("department_event_definitions")

    op.drop_index(
        "ix_user_notification_pref_events_business_id",
        table_name="user_notification_pref_events",
    )
    op.drop_index(
        "ix_user_notification_pref_events_department_id",
        table_name="user_notification_pref_events",
    )
    op.drop_index(
        "ix_user_notification_pref_events_user_id",
        table_name="user_notification_pref_events",
    )
    op.drop_table("user_notification_pref_events")

    op.drop_index(
        "ix_department_event_definitions_business_id",
        table_name="department_event_definitions",
    )
    op.drop_index(
        "ix_department_event_definitions_department_id",
        table_name="department_event_definitions",
    )
    op.drop_table("department_event_definitions")
