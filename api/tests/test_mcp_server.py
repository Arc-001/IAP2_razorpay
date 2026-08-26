import uuid
from contextlib import contextmanager
from datetime import UTC, datetime

import pytest

import mcp_server.server as mcp_server_module
from app.adapters.payment_provider import ChargeResult
from app.models import CartMandate, Customer, IntentMandate, Merchant, PaymentMandate, Product
from mcp_server.server import (
    accept_upsell,
    cancel_payment,
    check_payment_status,
    confirm_cart,
    confirm_intent,
    create_payment_link,
    decline_upsell,
    propose_cart,
    propose_intent,
    retry_payment,
    search_catalog,
    suggest_upsell,
)


@pytest.fixture(autouse=True)
def _use_test_db(monkeypatch, db_session):
    """MCP tools normally open their own SessionLocal() per call (there's no
    FastAPI request to hang a Depends(get_db) off) — redirect that to the
    same isolated, rolled-back test session everything else here uses."""

    @contextmanager
    def fake_db():
        yield db_session

    monkeypatch.setattr(mcp_server_module, "_db", fake_db)


class FakePaymentLinkAdapter:
    def create_charge(self, amount, currency, notes):
        return ChargeResult(
            reference="plink_fake",
            adapter="payment_link",
            client_payload={"short_url": "https://rzp.io/i/fake", "payment_link_id": "plink_fake"},
        )

    def verify(self, payload):
        return True


@pytest.fixture(autouse=True)
def _fake_payment_link_adapter(monkeypatch):
    monkeypatch.setattr(mcp_server_module, "PaymentLinkAdapter", FakePaymentLinkAdapter)


def _customer(db_session, saved_address=None) -> Customer:
    customer = Customer(name="Test", saved_address=saved_address)
    db_session.add(customer)
    db_session.commit()
    return customer


def _confirmed_intent(db_session, customer, budget_paise=None) -> IntentMandate:
    intent = IntentMandate(
        customer_id=customer.id,
        raw_text="x",
        structured_json={"budget_paise": budget_paise},
        status="confirmed",
        signature="s",
        confirmed_at=datetime.now(UTC),
    )
    db_session.add(intent)
    db_session.commit()
    return intent


def _confirmed_cart(db_session, intent, total_amount=10000) -> CartMandate:
    cart = CartMandate(
        intent_mandate_id=intent.id,
        items=[],
        total_amount=total_amount,
        shipping_address={"line1": "x"},
        status="confirmed",
        signature="s",
        confirmed_at=datetime.now(UTC),
    )
    db_session.add(cart)
    db_session.commit()
    return cart


def test_propose_intent_creates_draft(db_session):
    customer = _customer(db_session)

    result = propose_intent(
        product_query="wireless earbuds", quantity=1, budget_paise=300000, customer_id=str(customer.id)
    )

    assert result["status"] == "draft"
    assert result["structured"]["product_query"] == "wireless earbuds"
    row = db_session.get(IntentMandate, uuid.UUID(result["intent_id"]))
    assert row is not None


def test_propose_intent_defaults_to_demo_customer_when_none_given(db_session):
    result = propose_intent(product_query="a phone case")
    assert result["status"] == "draft"


def test_confirm_intent_signs_draft(db_session):
    customer = _customer(db_session)
    draft = propose_intent(product_query="earbuds", customer_id=str(customer.id))

    result = confirm_intent(draft["intent_id"])

    assert result["status"] == "confirmed"
    assert result["signature"] is not None


def test_confirm_intent_twice_returns_error_not_exception(db_session):
    customer = _customer(db_session)
    draft = propose_intent(product_query="earbuds", customer_id=str(customer.id))
    confirm_intent(draft["intent_id"])

    result = confirm_intent(draft["intent_id"])

    assert "error" in result


def test_confirm_intent_unknown_id_returns_error(db_session):
    result = confirm_intent(str(uuid.uuid4()))
    assert "error" in result


def test_search_catalog_returns_matches(db_session):
    merchant = Merchant(name="M")
    db_session.add(merchant)
    db_session.flush()
    db_session.add(Product(merchant_id=merchant.id, name="Power Bank", description=None, price=100000, stock=5))
    db_session.commit()

    result = search_catalog("power")

    assert result["products"][0]["name"] == "Power Bank"


def test_suggest_upsell_excludes_selected_product(db_session):
    merchant = Merchant(name="M")
    db_session.add(merchant)
    db_session.flush()
    main_item = Product(merchant_id=merchant.id, name="Power Bank", description=None, price=100000, stock=5)
    addon = Product(merchant_id=merchant.id, name="USB-C Cable", description=None, price=29900, stock=10)
    db_session.add_all([main_item, addon])
    db_session.commit()

    result = suggest_upsell([str(main_item.id)])

    names = [c["name"] for c in result["candidates"]]
    assert "USB-C Cable" in names
    assert "Power Bank" not in names


def test_accept_upsell_returns_product_details(db_session):
    merchant = Merchant(name="M")
    db_session.add(merchant)
    db_session.flush()
    addon = Product(merchant_id=merchant.id, name="USB-C Cable", description=None, price=29900, stock=10)
    db_session.add(addon)
    db_session.commit()

    result = accept_upsell(str(addon.id), quantity=2)

    assert result["accepted"] is True
    assert result["quantity"] == 2


def test_accept_upsell_unknown_product_returns_error(db_session):
    result = accept_upsell(str(uuid.uuid4()))
    assert "error" in result


def test_decline_upsell_acknowledges(db_session):
    assert decline_upsell() == {"accepted": False}


def test_propose_cart_creates_draft(db_session):
    merchant = Merchant(name="M")
    db_session.add(merchant)
    db_session.flush()
    product = Product(merchant_id=merchant.id, name="Power Bank", description=None, price=100000, stock=5)
    db_session.add(product)
    db_session.flush()
    customer = _customer(db_session, saved_address={"line1": "x"})
    intent = _confirmed_intent(db_session, customer)

    result = propose_cart(str(intent.id), [{"product_id": str(product.id), "quantity": 1}])

    assert result["status"] == "draft"
    assert result["total_amount"] == 104900  # + flat shipping fee


def test_propose_cart_rejects_unconfirmed_intent(db_session):
    customer = _customer(db_session)
    intent = IntentMandate(customer_id=customer.id, raw_text="x", structured_json={}, status="draft")
    db_session.add(intent)
    db_session.commit()

    result = propose_cart(str(intent.id), [])

    assert "confirmed" in result["error"]


def test_confirm_cart_signs_draft(db_session):
    customer = _customer(db_session, saved_address={"line1": "x"})
    intent = _confirmed_intent(db_session, customer)
    cart = CartMandate(
        intent_mandate_id=intent.id, items=[], total_amount=10000, shipping_address={"line1": "x"}, status="draft"
    )
    db_session.add(cart)
    db_session.commit()

    result = confirm_cart(str(cart.id))

    assert result["status"] == "confirmed"


def test_confirm_cart_budget_guard_returns_error(db_session):
    customer = _customer(db_session, saved_address={"line1": "x"})
    intent = _confirmed_intent(db_session, customer, budget_paise=5000)
    cart = CartMandate(
        intent_mandate_id=intent.id, items=[], total_amount=99999, shipping_address={"line1": "x"}, status="draft"
    )
    db_session.add(cart)
    db_session.commit()

    result = confirm_cart(str(cart.id))

    assert "exceeds intent budget" in result["error"]


def test_create_payment_link_returns_url(db_session):
    customer = _customer(db_session, saved_address={"line1": "x"})
    intent = _confirmed_intent(db_session, customer)
    cart = _confirmed_cart(db_session, intent)

    result = create_payment_link(str(cart.id))

    assert result["status"] == "pending"
    assert result["payment_link_url"] == "https://rzp.io/i/fake"


def test_create_payment_link_rejects_unconfirmed_cart(db_session):
    customer = _customer(db_session, saved_address={"line1": "x"})
    intent = _confirmed_intent(db_session, customer)
    cart = CartMandate(
        intent_mandate_id=intent.id, items=[], total_amount=10000, shipping_address={"line1": "x"}, status="draft"
    )
    db_session.add(cart)
    db_session.commit()

    result = create_payment_link(str(cart.id))

    assert "error" in result


def test_check_payment_status_reports_current_status(db_session):
    customer = _customer(db_session, saved_address={"line1": "x"})
    intent = _confirmed_intent(db_session, customer)
    cart = _confirmed_cart(db_session, intent)
    payment_id = create_payment_link(str(cart.id))["payment_id"]

    result = check_payment_status(payment_id)

    assert result["status"] == "pending"


def test_check_payment_status_unknown_id_returns_error(db_session):
    result = check_payment_status(str(uuid.uuid4()))
    assert "error" in result


def test_retry_payment_creates_new_link(db_session):
    customer = _customer(db_session, saved_address={"line1": "x"})
    intent = _confirmed_intent(db_session, customer)
    cart = _confirmed_cart(db_session, intent)

    result = retry_payment(str(cart.id))

    assert result["payment_link_url"] == "https://rzp.io/i/fake"


def test_cancel_payment_marks_cancelled(db_session):
    customer = _customer(db_session, saved_address={"line1": "x"})
    intent = _confirmed_intent(db_session, customer)
    cart = _confirmed_cart(db_session, intent)
    payment = PaymentMandate(cart_mandate_id=cart.id, razorpay_ref="plink_x", amount=10000, status="failed")
    db_session.add(payment)
    db_session.commit()

    result = cancel_payment(str(payment.id))

    assert result["status"] == "cancelled"


def test_cancel_payment_rejects_non_failed_payment(db_session):
    customer = _customer(db_session, saved_address={"line1": "x"})
    intent = _confirmed_intent(db_session, customer)
    cart = _confirmed_cart(db_session, intent)
    payment = PaymentMandate(cart_mandate_id=cart.id, razorpay_ref="plink_x", amount=10000, status="pending")
    db_session.add(payment)
    db_session.commit()

    result = cancel_payment(str(payment.id))

    assert "error" in result
