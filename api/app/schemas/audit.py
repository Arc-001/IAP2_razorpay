import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    mandate_type: str
    mandate_id: uuid.UUID
    from_state: str | None
    to_state: str | None
    actor: str | None
    payload_hash: str | None
    created_at: datetime


class TransactionSummary(BaseModel):
    intent_id: uuid.UUID
    raw_text: str | None
    status: str
    created_at: datetime


class TransactionAuditOut(BaseModel):
    intent_id: uuid.UUID
    intent_status: str
    intent_signature: str | None
    cart_ids: list[uuid.UUID]
    cart_signatures: list[str]
    payment_ids: list[uuid.UUID]
    payment_statuses: list[str]
    payment_signature_verified: list[bool]
    """payment_mandates has no HMAC .signature field (only signature_verified:
    bool) — this is the honest equivalent for payments: whether the Razorpay
    webhook signature was verified, not a JWT string like Intent/Cart carry."""
    entries: list[AuditLogOut]
