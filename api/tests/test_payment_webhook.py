import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime

import pytest

from app.config import settings
from app.models import AuditLog, CartMandate, Customer, IntentMandate, PaymentMandate
from app.services import payment_webhook as payment_webhook_module

WEBHOOK_SECRET = "test-webhook-secret"


@pytest.fixture(autouse=True)
def webhook_secret(monkeypatch):
    monkeypatch.setattr(settings, "razorpay_webhook_secret", WEBHOOK_SECRET)


def _sign(body: bytes) -> str:
    return hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()


def _webhook_body(event: str, payment_id: str, mandate_id: str, amount: int) -> bytes:
    payload = {
        "event": event,
        "payload": {
            "payment": {
                "entity": {"id": payment_id, "amount": amount, "notes": {"mandate_id": mandate_id}}
            }
        },
    }
    return json.dumps(payload).encode()


def _make_pending_payment(db_session, amount=44800) -> PaymentMandate:
    customer = Customer(name="Test Customer", saved_address={"line1": "x"})
    db_session.add(customer)
    db_session.flush()
    intent = IntentMandate(
        customer_id=customer.id,
        raw_text="t",
        structured_json={},
        status="confirmed",
        signature="s",
        confirmed_at=datetime.now(UTC),
    )
    db_session.add(intent)
    db_session.flush()
    cart = CartMandate(
        intent_mandate_id=intent.id,
        items=[],
        total_amount=amount,
        shipping_address={},
        status="confirmed",
        signature="s",
        confirmed_at=datetime.now(UTC),
    )
    db_session.add(cart)
    db_session.flush()
    payment = PaymentMandate(cart_mandate_id=cart.id, razorpay_ref="order_x", amount=amount, status="pending")
    db_session.add(payment)
    db_session.commit()
    return payment


def test_webhook_rejects_invalid_signature(client):
    body = _webhook_body("payment.captured", "pay_x", str(uuid.uuid4()), 100)

    response = client.post(
        "/api/webhooks/razorpay",
        content=body,
        headers={"X-Razorpay-Signature": "wrong-signature", "Content-Type": "application/json"},
    )

    assert response.status_code == 400


def test_webhook_captured_marks_payment_executed(client, db_session):
    payment = _make_pending_payment(db_session)
    body = _webhook_body("payment.captured", "pay_success1", str(payment.id), payment.amount)

    response = client.post(
        "/api/webhooks/razorpay",
        content=body,
        headers={"X-Razorpay-Signature": _sign(body), "Content-Type": "application/json"},
    )

    assert response.status_code == 200
    db_session.refresh(payment)
    assert payment.status == "executed"
    assert payment.razorpay_payment_id == "pay_success1"
    assert payment.signature_verified is True
    assert payment.resolved_at is not None


def test_webhook_failed_marks_payment_failed(client, db_session):
    payment = _make_pending_payment(db_session)
    body = _webhook_body("payment.failed", "pay_fail1", str(payment.id), payment.amount)

    response = client.post(
        "/api/webhooks/razorpay",
        content=body,
        headers={"X-Razorpay-Signature": _sign(body), "Content-Type": "application/json"},
    )

    assert response.status_code == 200
    db_session.refresh(payment)
    assert payment.status == "failed"


def test_webhook_ignores_unrelated_event(client, db_session):
    payment = _make_pending_payment(db_session)
    body = _webhook_body("order.paid", "pay_x", str(payment.id), payment.amount)

    response = client.post(
        "/api/webhooks/razorpay",
        content=body,
        headers={"X-Razorpay-Signature": _sign(body), "Content-Type": "application/json"},
    )

    assert response.status_code == 200
    db_session.refresh(payment)
    assert payment.status == "pending"


def test_webhook_unknown_mandate_id_is_ignored_not_error(client):
    body = _webhook_body("payment.captured", "pay_x", str(uuid.uuid4()), 100)

    response = client.post(
        "/api/webhooks/razorpay",
        content=body,
        headers={"X-Razorpay-Signature": _sign(body), "Content-Type": "application/json"},
    )

    assert response.status_code == 200


def test_webhook_is_idempotent_on_duplicate_delivery(client, db_session):
    payment = _make_pending_payment(db_session)
    body = _webhook_body("payment.captured", "pay_dup", str(payment.id), payment.amount)
    headers = {"X-Razorpay-Signature": _sign(body), "Content-Type": "application/json"}

    client.post("/api/webhooks/razorpay", content=body, headers=headers)
    response = client.post("/api/webhooks/razorpay", content=body, headers=headers)

    assert response.status_code == 200
    db_session.refresh(payment)
    assert payment.status == "executed"
    transitions = (
        db_session.query(AuditLog)
        .filter(AuditLog.mandate_type == "payment", AuditLog.mandate_id == payment.id)
        .all()
    )
    assert len(transitions) == 1  # not double-recorded on retry


def test_process_webhook_ignores_missing_mandate_id(db_session):
    result = payment_webhook_module.process_payment_webhook(db_session, "payment.captured", {"id": "pay_x"})
    assert result is None


def test_process_webhook_ignores_malformed_mandate_id(db_session):
    result = payment_webhook_module.process_payment_webhook(
        db_session, "payment.captured", {"id": "pay_x", "notes": {"mandate_id": "not-a-uuid"}}
    )
    assert result is None


def test_process_webhook_ignores_unknown_event_type(db_session):
    payment = _make_pending_payment(db_session)

    result = payment_webhook_module.process_payment_webhook(
        db_session, "refund.processed", {"id": "x", "notes": {"mandate_id": str(payment.id)}}
    )

    assert result is None
    db_session.refresh(payment)
    assert payment.status == "pending"
