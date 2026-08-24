"""initial schema

Revision ID: 847cdb675421
Revises: 
Create Date: 2026-08-24 17:05:50.760938

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

# revision identifiers, used by Alembic.
revision: str = '847cdb675421'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # gen_random_uuid() ships in pgcrypto; PG13+ core only has it once this is enabled.
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "merchants",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "products",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("merchant_id", pg.UUID(as_uuid=True), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("price", sa.Integer, nullable=False),  # smallest currency subunit (paise)
        sa.Column("currency", sa.Text, server_default="INR"),
        sa.Column("stock", sa.Integer),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "price_history",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("product_id", pg.UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("price", sa.Integer, nullable=False),
        sa.Column("changed_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "customers",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.Text),
        sa.Column("contact", sa.Text),
        sa.Column("saved_address", pg.JSONB),
    )

    op.create_table(
        "intent_mandates",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("customer_id", pg.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("raw_text", sa.Text),
        sa.Column("structured_json", pg.JSONB),
        sa.Column("status", sa.Text, nullable=False, server_default="draft"),
        sa.Column("signature", sa.Text),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("confirmed_at", sa.TIMESTAMP(timezone=True)),
        sa.CheckConstraint("status IN ('draft','confirmed','expired')", name="intent_mandates_status_check"),
    )

    op.create_table(
        "cart_mandates",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("intent_mandate_id", pg.UUID(as_uuid=True), sa.ForeignKey("intent_mandates.id"), nullable=False),
        sa.Column("items", pg.JSONB),
        sa.Column("total_amount", sa.Integer, nullable=False),
        sa.Column("shipping_address", pg.JSONB),
        sa.Column("status", sa.Text, nullable=False, server_default="draft"),
        sa.Column("signature", sa.Text),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("confirmed_at", sa.TIMESTAMP(timezone=True)),
        sa.CheckConstraint("status IN ('draft','confirmed')", name="cart_mandates_status_check"),
    )

    op.create_table(
        "payment_mandates",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("cart_mandate_id", pg.UUID(as_uuid=True), sa.ForeignKey("cart_mandates.id"), nullable=False),
        sa.Column("razorpay_ref", sa.Text),  # order_id or payment_link_id
        sa.Column("amount", sa.Integer, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("razorpay_payment_id", sa.Text),
        sa.Column("signature_verified", sa.Boolean, server_default=sa.false()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True)),
        sa.CheckConstraint("status IN ('pending','executed','failed')", name="payment_mandates_status_check"),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("mandate_type", sa.Text, nullable=False),
        sa.Column("mandate_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("from_state", sa.Text),
        sa.Column("to_state", sa.Text),
        sa.Column("actor", sa.Text),
        sa.Column("payload_hash", sa.Text),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("audit_log")
    op.drop_table("payment_mandates")
    op.drop_table("cart_mandates")
    op.drop_table("intent_mandates")
    op.drop_table("customers")
    op.drop_table("price_history")
    op.drop_table("products")
    op.drop_table("merchants")
