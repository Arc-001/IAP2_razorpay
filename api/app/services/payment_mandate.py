import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.adapters.payment_provider import ChargeResult, PaymentProvider
from app.adapters.standard_checkout import StandardCheckoutAdapter
from app.models import CartMandate, PaymentMandate
from app.services.audit import record_transition
from app.services.mandate_signing import hash_payload


def create_payment_for_cart(
    db: Session, cart_id: uuid.UUID, provider: PaymentProvider | None = None
) -> tuple[PaymentMandate, ChargeResult]:
    cart = db.get(CartMandate, cart_id)
    if cart is None:
        raise LookupError(f"cart mandate {cart_id} not found")
    if cart.status != "confirmed":
        raise ValueError(f"cart mandate must be confirmed before payment (status: '{cart.status}')")

    payment = PaymentMandate(cart_mandate_id=cart.id, amount=cart.total_amount, status="pending")
    db.add(payment)
    db.flush()

    provider = provider or StandardCheckoutAdapter()
    charge = provider.create_charge(
        amount=cart.total_amount,
        currency="INR",
        notes={"mandate_id": str(payment.id)},  # webhook correlation, CLAUDE.md §6.7
    )
    payment.razorpay_ref = charge.reference

    record_transition(db, "payment", payment.id, None, "pending", "system", charge.reference)
    db.commit()
    db.refresh(payment)
    return payment, charge


def get_payment_mandate(db: Session, payment_id: uuid.UUID) -> PaymentMandate | None:
    return db.get(PaymentMandate, payment_id)


def cancel_payment(db: Session, payment_id: uuid.UUID) -> PaymentMandate:
    """The human-facing half of the failure branch (CLAUDE.md §8 step 10):
    after a failed payment, offer retry or cancel — never fail silently.
    Only a failed payment can be cancelled; a pending/executed one has its
    own resolution path already."""
    payment = db.get(PaymentMandate, payment_id)
    if payment is None:
        raise LookupError(f"payment mandate {payment_id} not found")
    if payment.status != "failed":
        raise ValueError(f"only a failed payment can be cancelled (status: '{payment.status}')")

    payment.status = "cancelled"
    payment.resolved_at = datetime.now(UTC)

    payload_hash = hash_payload({"payment_id": str(payment.id), "reason": "customer cancelled after failure"})
    record_transition(db, "payment", payment.id, "failed", "cancelled", "user", payload_hash)
    db.commit()
    db.refresh(payment)
    return payment
