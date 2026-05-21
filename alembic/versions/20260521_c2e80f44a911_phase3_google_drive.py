"""phase 3: connected_google_accounts table + projects.drive_folder_*

Adds per-user OAuth credential storage (Phase 3 Task 3.3) plus the Drive
folder attachment columns on `projects`. Refresh tokens are Fernet-encrypted
before they land in `encrypted_refresh_token` — never stored plaintext.

Revision ID: c2e80f44a911
Revises: 40d16053cb3d
Create Date: 2026-05-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c2e80f44a911"
down_revision: Union[str, Sequence[str], None] = "40d16053cb3d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "connected_google_accounts",
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
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("google_email", sa.String(length=320), nullable=False),
        sa.Column("encrypted_refresh_token", sa.Text(), nullable=False),
        sa.Column("scopes", sa.Text(), nullable=False),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "provider", name="uq_connected_google_user_provider"),
    )
    op.create_index(
        "ix_connected_google_accounts_user_id",
        "connected_google_accounts",
        ["user_id"],
        unique=False,
    )

    op.add_column(
        "projects",
        sa.Column("drive_folder_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("drive_folder_url", sa.String(length=2048), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("projects", "drive_folder_url")
    op.drop_column("projects", "drive_folder_id")
    op.drop_index(
        "ix_connected_google_accounts_user_id",
        table_name="connected_google_accounts",
    )
    op.drop_table("connected_google_accounts")
