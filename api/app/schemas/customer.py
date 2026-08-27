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
