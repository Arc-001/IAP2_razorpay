"""add conversations

Revision ID: de0501e83090
Revises: 0d0ea64f3108
Create Date: 2026-08-27 19:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

# revision identifiers, used by Alembic.
revision: str = 'de0501e83090'
down_revision: str | Sequence[str] | None = '0d0ea64f3108'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "conversations",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("customer_id", pg.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("intent_id", pg.UUID(as_uuid=True), sa.ForeignKey("intent_mandates.id")),
        sa.Column("cart_id", pg.UUID(as_uuid=True), sa.ForeignKey("cart_mandates.id")),
        sa.Column("payment_id", pg.UUID(as_uuid=True), sa.ForeignKey("payment_mandates.id")),
        sa.Column("state", sa.Text, nullable=False, server_default="DRAFTING_INTENT"),
        sa.Column("title", sa.Text),
        sa.Column("history", pg.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("display_log", pg.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("conversations")
