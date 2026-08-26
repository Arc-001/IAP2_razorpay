import uuid
from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db import Base


# Python-side default, not server_default=func.now(): Postgres freezes
# now() to transaction start, so multiple rows inserted in one transaction
# (routine here — several commits per request, and test isolation runs a
# whole test in one transaction) get identical timestamps, making any
# ORDER BY created_at/changed_at comparison between them undefined. A
# client-side default calls the real wall clock per row instead.
def _now() -> datetime:
    return datetime.now(UTC)


class Merchant(Base):
    __tablename__ = "merchants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=_now)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    merchant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("merchants.id"))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    price: Mapped[int] = mapped_column(nullable=False)  # smallest currency subunit (paise)
    currency: Mapped[str] = mapped_column(Text, server_default="INR")
    stock: Mapped[int | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=_now)

    merchant: Mapped["Merchant"] = relationship()
    """Read-only convenience for cross-merchant comparison (CLAUDE.md §11
    P3.3) — search() has always spanned every merchant, but callers had no
    way to say *which* one a result came from until now."""

    @property
    def merchant_name(self) -> str:
        return self.merchant.name


class PriceHistory(Base):
    """Append-only. Powers the >10% price-rise re-confirmation rule (CLAUDE.md §5)."""

    __tablename__ = "price_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"))
    price: Mapped[int] = mapped_column(nullable=False)
    changed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=_now)


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    name: Mapped[str | None] = mapped_column(Text)
    contact: Mapped[str | None] = mapped_column(Text)
    saved_address: Mapped[dict | None] = mapped_column(JSONB)


class IntentMandate(Base):
    __tablename__ = "intent_mandates"
    __table_args__ = (CheckConstraint("status IN ('draft','confirmed','expired')", name="intent_mandates_status_check"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"))
    raw_text: Mapped[str | None] = mapped_column(Text)
    structured_json: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(Text, server_default="draft")
    signature: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=_now)
    confirmed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))


class CartMandate(Base):
    __tablename__ = "cart_mandates"
    __table_args__ = (CheckConstraint("status IN ('draft','confirmed')", name="cart_mandates_status_check"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    intent_mandate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("intent_mandates.id"))
    items: Mapped[dict | None] = mapped_column(JSONB)
    total_amount: Mapped[int] = mapped_column(nullable=False)
    shipping_address: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(Text, server_default="draft")
    signature: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=_now)
    confirmed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))


class PaymentMandate(Base):
    __tablename__ = "payment_mandates"
    __table_args__ = (
        CheckConstraint("status IN ('pending','executed','failed','cancelled')", name="payment_mandates_status_check"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    cart_mandate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cart_mandates.id"))
    razorpay_ref: Mapped[str | None] = mapped_column(Text)  # order_id or payment_link_id
    amount: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(Text, server_default="pending")
    razorpay_payment_id: Mapped[str | None] = mapped_column(Text)
    signature_verified: Mapped[bool] = mapped_column(server_default="false")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=_now)
    resolved_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))


class AuditLog(Base):
    """Append-only — every mandate transition is an INSERT, never an UPDATE (CLAUDE.md §3)."""

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    mandate_type: Mapped[str] = mapped_column(Text, nullable=False)
    mandate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    from_state: Mapped[str | None] = mapped_column(Text)
    to_state: Mapped[str | None] = mapped_column(Text)
    actor: Mapped[str | None] = mapped_column(Text)
    payload_hash: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=_now)
