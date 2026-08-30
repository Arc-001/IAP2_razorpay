"""add oauth refresh tokens

Revision ID: 85cbd8671b7f
Revises: 7d985ccef589
Create Date: 2026-08-30 15:54:00.971359

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

# revision identifiers, used by Alembic.
revision: str = '85cbd8671b7f'
down_revision: str | Sequence[str] | None = '7d985ccef589'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "oauth_refresh_tokens",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("token_hash", sa.Text, nullable=False, unique=True),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_id", sa.Text, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True)),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("oauth_refresh_tokens")
