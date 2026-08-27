import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db import Base
from app.models.mandates import _now


class Conversation(Base):
    """Persisted chat history (CLAUDE.md §13 / SCRUM-41) — history/display_log
    map directly onto ChatRequest.history and the frontend's DisplayEntry[]
    (web/src/lib/types.ts), so resuming a conversation needs no translation
    layer, just handing the same shapes back."""

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    intent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("intent_mandates.id"))
    cart_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("cart_mandates.id"))
    payment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("payment_mandates.id"))
    state: Mapped[str] = mapped_column(Text, nullable=False, server_default="DRAFTING_INTENT")
    title: Mapped[str | None] = mapped_column(Text)
    history: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    display_log: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=_now)
