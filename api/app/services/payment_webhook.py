import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import PaymentMandate
from app.services.audit import record_transition
from app.services.mandate_signing import hash_payload

_EVENT_TO_STATUS = {
    "payment.captured": "executed",
    "payment.failed": "failed",
}


def process_payment_webhook(db: Session, event: str, payment_entity: dict) -> PaymentMandate | None:
    """Only ever called after the webhook signature has already been verified
    (CLAUDE.md §6.7) — an unverified webhook is not proof of payment, so
    signature checking happens at the router before this is reached."""
    new_status = _EVENT_TO_STATUS.get(event)
    if new_status is None:
        return None  # event we don't act on (order.paid, refunds, etc.)

    mandate_id_str = (payment_entity.get("notes") or {}).get("mandate_id")
    if not mandate_id_str:
        return None
    try:
        mandate_id = uuid.UUID(mandate_id_str)
    except ValueError:
        return None

    payment = db.get(PaymentMandate, mandate_id)
    if payment is None:
        return None
    if payment.status != "pending":
        return payment  # already resolved — idempotent no-op on webhook retry

    payment.status = new_status
    payment.razorpay_payment_id = payment_entity.get("id")
    payment.signature_verified = True
    payment.resolved_at = datetime.now(UTC)

    payload_hash = hash_payload(
        {"event": event, "razorpay_payment_id": payment_entity.get("id"), "status": new_status}
    )
    record_transition(db, "payment", payment.id, "pending", new_status, "system", payload_hash)
    db.commit()
    db.refresh(payment)
    return payment
