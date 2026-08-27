"""add customer addresses

Revision ID: 3fbbd80b82c5
Revises: de0501e83090
Create Date: 2026-08-27 20:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

# revision identifiers, used by Alembic.
revision: str = '3fbbd80b82c5'
down_revision: str | Sequence[str] | None = 'de0501e83090'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "customer_addresses",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "customer_id", pg.UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("label", sa.Text),
        sa.Column("line1", sa.Text, nullable=False),
        sa.Column("line2", sa.Text),
        sa.Column("city", sa.Text),
        sa.Column("state", sa.Text),
        sa.Column("postal_code", sa.Text),
        sa.Column("country", sa.Text, nullable=False, server_default="IN"),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )

    # Best-effort backfill from customers.saved_address — a free-form JSONB
    # blob with no fixed key set (real data observed in this app uses keys
    # like {"street", "town"} as often as {"line1", "city"}). Only backfill
    # rows where a usable line1-equivalent exists; anything else stays
    # reachable solely via the legacy column, which is left in place as a
    # fallback (see _resolve_shipping_address in services/cart_mandate.py) —
    # not every row can be confidently migrated, and that's fine.
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, saved_address FROM customers WHERE saved_address IS NOT NULL")).fetchall()
    for customer_id, saved_address in rows:
        if not saved_address:
            continue
        line1 = saved_address.get("line1") or saved_address.get("street") or saved_address.get("address")
        if not line1:
            continue
        bind.execute(
            sa.text(
                "INSERT INTO customer_addresses (customer_id, line1, city, state, postal_code, country, is_default) "
                "VALUES (:customer_id, :line1, :city, :state, :postal_code, :country, true)"
            ),
            {
                "customer_id": customer_id,
                "line1": line1,
                "city": saved_address.get("city") or saved_address.get("town"),
                "state": saved_address.get("state"),
                "postal_code": saved_address.get("postal_code") or saved_address.get("pincode"),
                "country": saved_address.get("country") or "IN",
            },
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("customer_addresses")
