import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db import Base
from app.models.mandates import _now


class User(Base):
    """A login-capable account. Separate from Customer/Merchant (the commerce
    domain entities) rather than merged into them — an admin has no natural
    home in either, and this keeps auth columns off tables already deeply
    embedded as FKs throughout the mandate chain."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('admin','merchant','customer')", name="users_role_check"),
        CheckConstraint(
            "(role = 'customer' AND customer_id IS NOT NULL AND merchant_id IS NULL) OR "
            "(role = 'merchant' AND merchant_id IS NOT NULL AND customer_id IS NULL) OR "
            "(role = 'admin' AND customer_id IS NULL AND merchant_id IS NULL)",
            name="users_role_link_check",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), unique=True)
    merchant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("merchants.id"), unique=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=_now)
    last_login_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
