import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CartItemRequest(BaseModel):
    product_id: uuid.UUID
    quantity: int = Field(ge=1)


class CartDraftRequest(BaseModel):
    intent_mandate_id: uuid.UUID
    items: list[CartItemRequest]
    shipping_address: dict | None = None
    acknowledge_price_change: bool = False


class CartMandateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    intent_mandate_id: uuid.UUID
    items: list[dict] | None
    total_amount: int
    shipping_address: dict | None
    status: str
    signature: str | None
    created_at: datetime
    confirmed_at: datetime | None
