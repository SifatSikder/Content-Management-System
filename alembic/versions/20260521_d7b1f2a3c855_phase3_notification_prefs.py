"""phase 3: user_notification_prefs table

Opt-out per-event notification toggles (Phase 3 Task 3.5). One row per user;
each boolean defaults to true so the user sees notifications until they
explicitly mute an event.

Revision ID: d7b1f2a3c855
Revises: c2e80f44a911
Create Date: 2026-05-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d7b1f2a3c855"
down_revision: Union[str, Sequence[str], None] = "c2e80f44a911"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PUSH_COLS = [
    "push_project_created",
    "push_script_submitted",
    "push_script_locked",
    "push_cut_uploaded",
    "push_cut_comment",
    "push_cut_approved",
    "push_cut_changes_requested",
    "push_project_published",
    "push_project_stuck",
]


def upgrade() -> None:
    op.create_table(
        "user_notification_prefs",
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
        *[
            sa.Column(col, sa.Boolean(), nullable=False, server_default=sa.text("true"))
            for col in PUSH_COLS
        ],
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_user_notification_prefs_user_id"),
    )
    op.create_index(
        "ix_user_notification_prefs_user_id",
        "user_notification_prefs",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_user_notification_prefs_user_id",
        table_name="user_notification_prefs",
    )
    op.drop_table("user_notification_prefs")
