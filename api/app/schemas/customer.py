import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ConversationSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str | None
    state: str
    created_at: datetime
    updated_at: datetime


class ConversationDetailOut(ConversationSummaryOut):
    intent_id: uuid.UUID | None
    cart_id: uuid.UUID | None
    payment_id: uuid.UUID | None
    history: list[dict]
    display_log: list[dict]


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str | None
    contact: str | None


class ProfileUpdate(BaseModel):
    name: str | None = None
    contact: str | None = None


class AddressIn(BaseModel):
    label: str | None = None
    line1: str
    line2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str = "IN"
    is_default: bool = False


class AddressUpdate(BaseModel):
    label: str | None = None
    line1: str | None = None
    line2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None
    is_default: bool | None = None


class AddressOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    label: str | None
    line1: str
    line2: str | None
    city: str | None
    state: str | None
    postal_code: str | None
    country: str
    is_default: bool
    created_at: datetime
