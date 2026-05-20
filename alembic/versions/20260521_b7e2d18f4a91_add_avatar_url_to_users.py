"""add avatar_url column to users

Cached from Google OAuth `profile.picture` so credentials-only sessions
still display the user's Google avatar.

Revision ID: b7e2d18f4a91
Revises: a4f1c0e02b3a
Create Date: 2026-05-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7e2d18f4a91"
down_revision: Union[str, Sequence[str], None] = "a4f1c0e02b3a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_url", sa.String(length=2048), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "avatar_url")
