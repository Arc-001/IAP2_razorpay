import uuid
from datetime import UTC, datetime

import pytest

from app.adapters.payment_provider import ChargeResult
from app.models import AuditLog, CartMandate, Customer, IntentMandate, PaymentMandate
from app.services import payment_mandate as payment_mandate_module
from app.services.payment_mandate import cancel_payment


class FakeProvider:
    def __init__(self):
        self.calls = []

    def create_charge(self, amount, currency, notes):
        self.calls.append({"amount": amount, "currency": currency, "notes": notes})
        return ChargeResult(
            reference="order_fake999",
            adapter="standard_checkout",
            client_payload={"key_id": "rzp_test_fake", "order_id": "order_fake999", "amount": amount, "currency": currency},
        )

    def verify(self, payload):
        return True


@pytest.fixture(autouse=True)
def fake_provider(monkeypatch):
    fake = FakeProvider()
    monkeypatch.setattr(payment_mandate_module, "StandardCheckoutAdapter", lambda: fake)
    return fake


def _make_cart(db_session, status="confirmed", total_amount=44800) -> CartMandate:
    customer = Customer(name="Test Customer", saved_address={"line1": "x"})
    db_session.add(customer)
    db_session.flush()
    intent = IntentMandate(
        customer_id=customer.id,
        raw_text="test",
        structured_json={"product_query": "x", "quantity": 1, "budget_paise": None, "constraints": []},
        status="confirmed",
        signature="fake-sig",
        confirmed_at=datetime.now(UTC),
    )
    db_session.add(intent)
    db_session.flush()
    cart = CartMandate(
        intent_mandate_id=intent.id,
        items=[{"product_id": str(uuid.uuid4()), "name": "Test Item", "unit_price": total_amount, "quantity": 1, "line_total": total_amount}],
        total_amount=total_amount,
        shipping_address={"line1": "x"},
        status=status,
        signature="fake-sig" if status == "confirmed" else None,
        confirmed_at=datetime.now(UTC) if status == "confirmed" else None,
    )
    db_session.add(cart)
    db_session.commit()
    return cart


def test_create_payment_for_confirmed_cart(client, db_session, fake_provider):
    cart = _make_cart(db_session, total_amount=44800)

    response = client.post("/api/payment", json={"cart_mandate_id": str(cart.id)})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending"
    assert body["amount"] == 44800
    assert body["razorpay_ref"] == "order_fake999"
    assert body["client_payload"]["order_id"] == "order_fake999"


def test_notes_carry_mandate_id_for_webhook_correlation(client, db_session, fake_provider):
    cart = _make_cart(db_session)

    body = client.post("/api/payment", json={"cart_mandate_id": str(cart.id)}).json()

    assert fake_provider.calls[0]["notes"]["mandate_id"] == body["id"]


def test_create_payment_rejects_unconfirmed_cart(client, db_session):
    cart = _make_cart(db_session, status="draft")

    response = client.post("/api/payment", json={"cart_mandate_id": str(cart.id)})

    assert response.status_code == 400
    assert "confirmed" in response.json()["detail"]


def test_create_payment_rejects_unknown_cart(client):
    response = client.post("/api/payment", json={"cart_mandate_id": str(uuid.uuid4())})
    assert response.status_code == 404


def test_get_payment_after_create(client, db_session):
    cart = _make_cart(db_session)
    created = client.post("/api/payment", json={"cart_mandate_id": str(cart.id)}).json()

    response = client.get(f"/api/payment/{created['id']}")

    assert response.status_code == 200
    assert response.json()["razorpay_ref"] == "order_fake999"


def test_get_payment_not_found(client):
    response = client.get(f"/api/payment/{uuid.uuid4()}")
    assert response.status_code == 404


def test_cancel_payment_marks_cancelled_and_records_audit(db_session):
    cart = _make_cart(db_session)
    payment = PaymentMandate(cart_mandate_id=cart.id, razorpay_ref="order_x", amount=cart.total_amount, status="failed")
    db_session.add(payment)
    db_session.commit()

    result = cancel_payment(db_session, payment.id)

    assert result.status == "cancelled"
    assert result.resolved_at is not None
    row = (
        db_session.query(AuditLog)
        .filter(AuditLog.mandate_type == "payment", AuditLog.mandate_id == payment.id)
        .one()
    )
    assert row.from_state == "failed"
    assert row.to_state == "cancelled"
    assert row.actor == "user"


def test_cancel_payment_rejects_non_failed_payment(db_session):
    cart = _make_cart(db_session)
    payment = PaymentMandate(cart_mandate_id=cart.id, razorpay_ref="order_x", amount=cart.total_amount, status="pending")
    db_session.add(payment)
    db_session.commit()

    with pytest.raises(ValueError, match="only a failed payment can be cancelled"):
        cancel_payment(db_session, payment.id)


def test_cancel_payment_rejects_unknown_payment(db_session):
    with pytest.raises(LookupError):
        cancel_payment(db_session, uuid.uuid4())


def test_audit_log_records_pending_transition(client, db_session):
    cart = _make_cart(db_session)
    created = client.post("/api/payment", json={"cart_mandate_id": str(cart.id)}).json()

    row = (
        db_session.query(AuditLog)
        .filter(AuditLog.mandate_type == "payment", AuditLog.mandate_id == uuid.UUID(created["id"]))
        .one()
    )
    assert row.to_state == "pending"
    assert row.from_state is None
