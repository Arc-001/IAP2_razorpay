"""add product category and tags

Revision ID: 7d985ccef589
Revises: 3fbbd80b82c5
Create Date: 2026-08-27 20:40:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

# revision identifiers, used by Alembic.
revision: str = '7d985ccef589'
down_revision: str | Sequence[str] | None = '3fbbd80b82c5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("products", sa.Column("category", sa.Text))
    op.add_column(
        "products", sa.Column("tags", pg.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("products", "tags")
    op.drop_column("products", "category")
