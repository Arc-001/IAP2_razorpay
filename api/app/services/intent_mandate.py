import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import Customer, IntentMandate
from app.schemas.intent import IntentExtraction
from app.services.audit import record_transition
from app.services.intent_extraction import extract_intent
from app.services.mandate_signing import hash_payload, sign_mandate


def _default_customer(db: Session) -> Customer:
    """Phase 1 has no signup flow yet — fall back to a single demo customer,
    same pattern as the catalog's default-merchant fallback."""
    customer = db.query(Customer).first()
    if customer is None:
        customer = Customer(name="Demo Customer")
        db.add(customer)
        db.flush()
    return customer


def _resolve_customer(db: Session, customer_id: uuid.UUID | None) -> Customer:
    if customer_id is not None:
        customer = db.get(Customer, customer_id)
        if customer is None:
            raise ValueError(f"customer {customer_id} not found")
        return customer
    return _default_customer(db)


def create_draft_intent_from_structured(
    db: Session, customer_id: uuid.UUID | None, raw_text: str, structured: IntentExtraction
) -> IntentMandate:
    """Persistence only — no LLM call. Used directly by the orchestrator's
    propose_intent tool handler, where the model's own tool-call arguments
    already *are* the extraction, so re-extracting would be a redundant
    second LLM call."""
    customer = _resolve_customer(db, customer_id)

    mandate = IntentMandate(
        customer_id=customer.id,
        raw_text=raw_text,
        structured_json=structured.model_dump(),
        status="draft",
    )
    db.add(mandate)
    db.flush()

    record_transition(
        db, "intent", mandate.id, None, "draft", "customer", hash_payload(mandate.structured_json)
    )
    db.commit()
    db.refresh(mandate)
    return mandate


def create_draft_intent(db: Session, raw_text: str, customer_id: uuid.UUID | None) -> IntentMandate:
    extraction = extract_intent(raw_text)
    structured = IntentExtraction(**extraction.model_dump(exclude={"raw_text"}))
    return create_draft_intent_from_structured(db, customer_id, raw_text, structured)


def get_intent_mandate(db: Session, mandate_id: uuid.UUID) -> IntentMandate | None:
    return db.get(IntentMandate, mandate_id)


def confirm_intent(db: Session, mandate_id: uuid.UUID) -> IntentMandate:
    """HITL confirmation gate — CLAUDE.md §1/§8: only after the human confirms
    does the Intent become an HMAC-signed, immutable row."""
    mandate = db.get(IntentMandate, mandate_id)
    if mandate is None:
        raise ValueError(f"intent mandate {mandate_id} not found")
    if mandate.status != "draft":
        raise ValueError(f"cannot confirm intent mandate in status '{mandate.status}'")

    payload_hash = hash_payload(mandate.structured_json)
    mandate.signature = sign_mandate("intent", mandate.id, payload_hash)
    mandate.status = "confirmed"
    mandate.confirmed_at = datetime.now(UTC)

    record_transition(db, "intent", mandate.id, "draft", "confirmed", "customer", payload_hash)
    db.commit()
    db.refresh(mandate)
    return mandate
