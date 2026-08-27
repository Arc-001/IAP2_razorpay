import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import CartMandate, IntentMandate, PaymentMandate
from app.services.audit import list_recent_transactions


@dataclass(frozen=True)
class OrderSummary:
    """A customer-facing view of one transaction — lighter than
    TransactionAuditTrail (services/audit.py): no audit_log entries, since
    that level of detail is an admin concern (SCRUM-45), not a buyer's order
    history. Picks the most recent cart/payment per intent, since in
    practice an intent has at most one live cart at a time (revisable
    drafts supersede the prior one rather than accumulating)."""

    intent: IntentMandate
    cart: CartMandate | None
    payment: PaymentMandate | None


def list_customer_orders(db: Session, customer_id: uuid.UUID, limit: int = 50) -> list[OrderSummary]:
    intents = list_recent_transactions(db, customer_id=customer_id, limit=limit)

    summaries = []
    for intent in intents:
        cart = (
            db.query(CartMandate)
            .filter(CartMandate.intent_mandate_id == intent.id)
            .order_by(CartMandate.created_at.desc())
            .first()
        )
        payment = None
        if cart is not None:
            payment = (
                db.query(PaymentMandate)
                .filter(PaymentMandate.cart_mandate_id == cart.id)
                .order_by(PaymentMandate.created_at.desc())
                .first()
            )
        summaries.append(OrderSummary(intent=intent, cart=cart, payment=payment))
    return summaries
