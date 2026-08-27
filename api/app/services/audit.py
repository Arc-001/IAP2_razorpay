"""Append-only audit trail (CLAUDE.md §3.2) — every mandate transition is an
INSERT here, never an UPDATE to this table. This module also holds the read
side (SCRUM-26): audit_log has no FK back to a single "transaction" id, so
reconstructing one means walking the intent -> cart(s) -> payment(s) chain
and pulling every row that touches any mandate in it."""

import uuid
from dataclasses import dataclass

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import AuditLog, CartMandate, IntentMandate, PaymentMandate


def record_transition(
    db: Session,
    mandate_type: str,
    mandate_id: uuid.UUID,
    from_state: str | None,
    to_state: str,
    actor: str,
    payload_hash: str,
) -> None:
    db.add(
        AuditLog(
            mandate_type=mandate_type,
            mandate_id=mandate_id,
            from_state=from_state,
            to_state=to_state,
            actor=actor,
            payload_hash=payload_hash,
        )
    )


def list_recent_transactions(
    db: Session, customer_id: uuid.UUID | None = None, limit: int = 50
) -> list[IntentMandate]:
    """Each intent mandate is the root of one transaction (CLAUDE.md §5,
    §8) — carts and payments always trace back to exactly one. customer_id
    is optional: the admin view (SCRUM-45) lists across everyone, while a
    customer's own order history (SCRUM-43) needs it scoped to just them."""
    query = db.query(IntentMandate)
    if customer_id is not None:
        query = query.filter(IntentMandate.customer_id == customer_id)
    return query.order_by(IntentMandate.created_at.desc()).limit(limit).all()


@dataclass(frozen=True)
class TransactionAuditTrail:
    intent: IntentMandate
    carts: list[CartMandate]
    payments: list[PaymentMandate]
    entries: list[AuditLog]


def get_transaction_audit_trail(db: Session, intent_id: uuid.UUID) -> TransactionAuditTrail:
    intent = db.get(IntentMandate, intent_id)
    if intent is None:
        raise LookupError(f"intent mandate {intent_id} not found")

    carts = db.query(CartMandate).filter(CartMandate.intent_mandate_id == intent_id).all()
    cart_ids = [c.id for c in carts]
    payments = (
        db.query(PaymentMandate).filter(PaymentMandate.cart_mandate_id.in_(cart_ids)).all() if cart_ids else []
    )
    payment_ids = [p.id for p in payments]

    filters = [(AuditLog.mandate_type == "intent") & (AuditLog.mandate_id == intent_id)]
    if cart_ids:
        filters.append((AuditLog.mandate_type == "cart") & (AuditLog.mandate_id.in_(cart_ids)))
    if payment_ids:
        filters.append((AuditLog.mandate_type == "payment") & (AuditLog.mandate_id.in_(payment_ids)))

    entries = db.query(AuditLog).filter(or_(*filters)).order_by(AuditLog.created_at).all()
    return TransactionAuditTrail(intent=intent, carts=carts, payments=payments, entries=entries)
