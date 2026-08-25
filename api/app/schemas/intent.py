from pydantic import BaseModel, Field


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
