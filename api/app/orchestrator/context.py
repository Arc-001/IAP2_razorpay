import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class MandateContext:
    """The IDs threaded through a conversation. The model never supplies
    these itself — tool handlers read/update them, never trust arguments
    for mandate identity."""

    customer_id: uuid.UUID | None = None
    intent_id: uuid.UUID | None = None
    cart_id: uuid.UUID | None = None
    payment_id: uuid.UUID | None = None


@dataclass(frozen=True)
class ToolResult:
    output: dict
    context: MandateContext
