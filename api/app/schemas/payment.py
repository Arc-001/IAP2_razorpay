import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PaymentChargeRequest(BaseModel):
    cart_mandate_id: uuid.UUID


class PaymentMandateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    cart_mandate_id: uuid.UUID
    razorpay_ref: str | None
    amount: int
    status: str
    razorpay_payment_id: str | None
    signature_verified: bool
    created_at: datetime
    resolved_at: datetime | None


class PaymentChargeResponse(PaymentMandateOut):
    client_payload: dict
