"""State-gated tool exposure (CLAUDE.md §7). No separate sessions table —
state is derived from which mandate rows exist and their status, the same
way audit_log *is* the audit trail rather than a parallel log."""

import uuid
from enum import StrEnum

from sqlalchemy.orm import Session

from app.models import CartMandate, IntentMandate, PaymentMandate


class AgentState(StrEnum):
    DRAFTING_INTENT = "DRAFTING_INTENT"
    AWAITING_INTENT_OK = "AWAITING_INTENT_OK"
    BUILDING_CART = "BUILDING_CART"
    AWAITING_CART_OK = "AWAITING_CART_OK"
    EXECUTING_PAYMENT = "EXECUTING_PAYMENT"
    TERMINAL = "TERMINAL"


def derive_state(
    db: Session,
    intent_id: uuid.UUID | None,
    cart_id: uuid.UUID | None,
    payment_id: uuid.UUID | None,
) -> AgentState:
    if payment_id is not None:
        payment = db.get(PaymentMandate, payment_id)
        if payment is None:
            raise LookupError(f"payment mandate {payment_id} not found")
        if payment.status in ("executed", "failed"):
            return AgentState.TERMINAL
        return AgentState.EXECUTING_PAYMENT

    if cart_id is not None:
        cart = db.get(CartMandate, cart_id)
        if cart is None:
            raise LookupError(f"cart mandate {cart_id} not found")
        if cart.status == "confirmed":
            return AgentState.EXECUTING_PAYMENT
        return AgentState.AWAITING_CART_OK

    if intent_id is not None:
        intent = db.get(IntentMandate, intent_id)
        if intent is None:
            raise LookupError(f"intent mandate {intent_id} not found")
        if intent.status == "confirmed":
            return AgentState.BUILDING_CART
        return AgentState.AWAITING_INTENT_OK

    return AgentState.DRAFTING_INTENT
