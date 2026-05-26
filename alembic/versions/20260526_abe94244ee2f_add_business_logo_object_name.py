"""add_business_logo_object_name

Revision ID: abe94244ee2f
Revises: d772f245fe78
Create Date: 2026-05-26 16:04:08.408148

Adds `businesses.logo_object_name` for the GCS object key of a business
logo image. Signed read URLs are minted on response; nothing about the
logo lives outside this column + the GCS blob it points to.

Autogenerate also surfaced a pile of unrelated pre-existing drift (orphan
`business_id` columns on script/edit/shoot/participant tables, etc.); that
drift is out of scope here and intentionally not touched.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'abe94244ee2f'
down_revision: Union[str, Sequence[str], None] = 'd772f245fe78'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "businesses",
        sa.Column("logo_object_name", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("businesses", "logo_object_name")
