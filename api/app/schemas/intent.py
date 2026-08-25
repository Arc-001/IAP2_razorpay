import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class IntentExtraction(BaseModel):
    """Structured Intent — CLAUDE.md §1: "what the user wants + constraints
    (budget, product criteria)". Produced by propose_intent tool-calling;
    signed into an intent_mandates row only after human confirmation (§11 P1.3)."""

    product_query: str = Field(description="What the customer is looking for, in searchable terms")
    quantity: int = Field(default=1, ge=1)
    budget_paise: int | None = Field(
        default=None, description="Max total budget in paise (INR smallest unit), null if unspecified"
    )
    constraints: list[str] = Field(
        default_factory=list, description="Other stated preferences, e.g. color, features, brand"
    )


class IntentExtractionRequest(BaseModel):
    raw_text: str


class IntentExtractionResponse(IntentExtraction):
    raw_text: str


class IntentDraftRequest(BaseModel):
    raw_text: str
    customer_id: uuid.UUID | None = None


class IntentMandateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    customer_id: uuid.UUID
    raw_text: str | None
    structured_json: dict | None
    status: str
    signature: str | None
    created_at: datetime
    confirmed_at: datetime | None
