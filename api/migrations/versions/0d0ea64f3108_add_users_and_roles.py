"""add users and roles

Revision ID: 0d0ea64f3108
Revises: 3b9dfb7fb5dd
Create Date: 2026-08-27 18:31:18.507239

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

# revision identifiers, used by Alembic.
revision: str = '0d0ea64f3108'
down_revision: str | Sequence[str] | None = '3b9dfb7fb5dd'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "users",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.Text, nullable=False, unique=True),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("role", sa.Text, nullable=False),
        sa.Column("customer_id", pg.UUID(as_uuid=True), sa.ForeignKey("customers.id"), unique=True),
        sa.Column("merchant_id", pg.UUID(as_uuid=True), sa.ForeignKey("merchants.id"), unique=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("last_login_at", sa.TIMESTAMP(timezone=True)),
        sa.CheckConstraint("role IN ('admin','merchant','customer')", name="users_role_check"),
        sa.CheckConstraint(
            "(role = 'customer' AND customer_id IS NOT NULL AND merchant_id IS NULL) OR "
            "(role = 'merchant' AND merchant_id IS NOT NULL AND customer_id IS NULL) OR "
            "(role = 'admin' AND customer_id IS NULL AND merchant_id IS NULL)",
            name="users_role_link_check",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("users")
