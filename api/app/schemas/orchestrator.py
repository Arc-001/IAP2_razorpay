import uuid

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    conversation_id: uuid.UUID | None = None
    intent_id: uuid.UUID | None = None
    cart_id: uuid.UUID | None = None
    payment_id: uuid.UUID | None = None
    history: list[dict] = []


class ChatResponse(BaseModel):
    state: str
    reply: str
    conversation_id: uuid.UUID
    customer_id: uuid.UUID | None
    intent_id: uuid.UUID | None
    cart_id: uuid.UUID | None
    payment_id: uuid.UUID | None
    tool_calls: list[dict]
    new_messages: list[dict]
    """Append verbatim to the history you send on the next turn."""
