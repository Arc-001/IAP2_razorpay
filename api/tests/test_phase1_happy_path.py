"""SCRUM-22 / CLAUDE.md §11 P1.7 — Phase 1 exit criteria: the full happy
path (Intent -> Cart -> Payment -> webhook outcome) works end-to-end on
the website surface, and every transition along the way writes an
append-only audit_log row. This is the one test that walks the entire
chain in a single flow, rather than verifying each piece in isolation."""

import hashlib
import hmac
import json

import pytest

from app.adapters.payment_provider import ChargeResult
from app.models import AuditLog, Merchant, Product
from app.schemas.intent import IntentExtractionResponse
from app.services import intent_mandate as intent_mandate_module
from app.services import payment_mandate as payment_mandate_module
from app.services.mandate_signing import verify_mandate

WEBHOOK_SECRET = "phase1-test-secret"

FAKE_EXTRACTION = IntentExtractionResponse(
    raw_text="I want a power bank, budget 2000 rupees",
    product_query="power bank",
    quantity=1,
    budget_paise=200000,
    constraints=[],
)


class FakeProvider:
    def create_charge(self, amount, currency, notes):
        return ChargeResult(
            reference="order_phase1_fake",
            adapter="standard_checkout",
            client_payload={"key_id": "rzp_test_fake", "order_id": "order_phase1_fake", "amount": amount, "currency": currency},
        )

    def verify(self, payload):
        return True


@pytest.fixture(autouse=True)
def mocks(monkeypatch):
    monkeypatch.setattr(intent_mandate_module, "extract_intent", lambda raw_text: FAKE_EXTRACTION)
    monkeypatch.setattr(payment_mandate_module, "StandardCheckoutAdapter", FakeProvider)
    from app.config import settings

    monkeypatch.setattr(settings, "razorpay_webhook_secret", WEBHOOK_SECRET)


def _sign(body: bytes) -> str:
    return hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()


def test_full_happy_path_writes_complete_audit_trail(client, db_session):
    # Catalog: one merchant, one product
    merchant = Merchant(name="TechBazaar")
    db_session.add(merchant)
    db_session.flush()
    product = Product(merchant_id=merchant.id, name="Power Bank 10000mAh", description=None, price=149900, stock=10)
    db_session.add(product)
    db_session.commit()

    # 1. Intent: draft -> confirm
    intent = client.post("/api/intent", json={"raw_text": FAKE_EXTRACTION.raw_text}).json()
    assert intent["status"] == "draft"
    intent = client.post(f"/api/intent/{intent['id']}/confirm").json()
    assert intent["status"] == "confirmed"
    assert verify_mandate(intent["signature"])["mandate_type"] == "intent"

    # 2. Cart: draft (with address) -> confirm
    cart = client.post(
        "/api/cart",
        json={
            "intent_mandate_id": intent["id"],
            "items": [{"product_id": product.id.hex, "quantity": 1}],
            "shipping_address": {"line1": "1 Test St"},
        },
    ).json()
    assert cart["status"] == "draft"
    assert cart["total_amount"] == 149900 + 4900  # item + flat shipping
    cart = client.post(f"/api/cart/{cart['id']}/confirm").json()
    assert cart["status"] == "confirmed"
    assert verify_mandate(cart["signature"])["mandate_type"] == "cart"

    # 3. Payment: pending
    payment = client.post("/api/payment", json={"cart_mandate_id": cart["id"]}).json()
    assert payment["status"] == "pending"
    assert payment["razorpay_ref"] == "order_phase1_fake"

    # 4. Webhook outcome: pending -> executed
    body = json.dumps(
        {
            "event": "payment.captured",
            "payload": {
                "payment": {"entity": {"id": "pay_phase1_fake", "amount": payment["amount"], "notes": {"mandate_id": payment["id"]}}}
            },
        }
    ).encode()
    webhook_response = client.post(
        "/api/webhooks/razorpay",
        content=body,
        headers={"X-Razorpay-Signature": _sign(body), "Content-Type": "application/json"},
    )
    assert webhook_response.status_code == 200

    final_payment = client.get(f"/api/payment/{payment['id']}").json()
    assert final_payment["status"] == "executed"
    assert final_payment["razorpay_payment_id"] == "pay_phase1_fake"
    assert final_payment["signature_verified"] is True

    # Full audit trail: every transition is a row, in order, none skipped
    rows = db_session.query(AuditLog).order_by(AuditLog.created_at).all()
    transitions = [(r.mandate_type, r.from_state, r.to_state) for r in rows]
    assert transitions == [
        ("intent", None, "draft"),
        ("intent", "draft", "confirmed"),
        ("cart", None, "draft"),
        ("cart", "draft", "confirmed"),
        ("payment", None, "pending"),
        ("payment", "pending", "executed"),
    ]
    # Never an UPDATE — every row is a fresh INSERT, so mandate_id groups cleanly
    assert len({r.mandate_id for r in rows}) == 3  # one id per mandate (intent, cart, payment)
