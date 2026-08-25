import uuid
from datetime import UTC, datetime

from app.models import Customer, IntentMandate, Merchant, Product
from app.services.cart_mandate import SHIPPING_FEE_PAISE
from app.services.mandate_signing import verify_mandate


def _make_customer(db_session, saved_address=None) -> Customer:
    customer = Customer(name="Test Customer", saved_address=saved_address)
    db_session.add(customer)
    db_session.commit()
    return customer


def _make_intent(db_session, customer, status="confirmed", budget_paise=None) -> IntentMandate:
    intent = IntentMandate(
        customer_id=customer.id,
        raw_text="test request",
        structured_json={
            "product_query": "test",
            "quantity": 1,
            "budget_paise": budget_paise,
            "constraints": [],
        },
        status=status,
        signature="fake-sig" if status == "confirmed" else None,
        confirmed_at=datetime.now(UTC) if status == "confirmed" else None,
    )
    db_session.add(intent)
    db_session.commit()
    return intent


def _make_product(db_session, price=49900) -> Product:
    merchant = Merchant(name="Test Merchant")
    db_session.add(merchant)
    db_session.flush()
    product = Product(merchant_id=merchant.id, name="Phone Case", description=None, price=price, stock=10)
    db_session.add(product)
    db_session.commit()
    return product


def test_draft_cart_uses_saved_address_automatically(client, db_session):
    customer = _make_customer(db_session, saved_address={"line1": "123 Main St", "city": "Pune"})
    intent = _make_intent(db_session, customer)
    product = _make_product(db_session, price=49900)

    response = client.post(
        "/api/cart",
        json={"intent_mandate_id": str(intent.id), "items": [{"product_id": str(product.id), "quantity": 2}]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["shipping_address"] == {"line1": "123 Main St", "city": "Pune"}
    assert body["total_amount"] == 49900 * 2 + SHIPPING_FEE_PAISE
    assert body["items"][0]["quantity"] == 2
    assert body["status"] == "draft"
    assert body["signature"] is None


def test_draft_cart_requires_address_when_none_available(client, db_session):
    customer = _make_customer(db_session, saved_address=None)
    intent = _make_intent(db_session, customer)
    product = _make_product(db_session)

    response = client.post(
        "/api/cart",
        json={"intent_mandate_id": str(intent.id), "items": [{"product_id": str(product.id), "quantity": 1}]},
    )

    assert response.status_code == 400
    assert "address" in response.json()["detail"]


def test_draft_cart_persists_provided_address_for_reuse(client, db_session):
    customer = _make_customer(db_session, saved_address=None)
    intent = _make_intent(db_session, customer)
    product = _make_product(db_session)

    response = client.post(
        "/api/cart",
        json={
            "intent_mandate_id": str(intent.id),
            "items": [{"product_id": str(product.id), "quantity": 1}],
            "shipping_address": {"line1": "45 New Rd", "city": "Mumbai"},
        },
    )

    assert response.status_code == 200
    db_session.refresh(customer)
    assert customer.saved_address == {"line1": "45 New Rd", "city": "Mumbai"}


def test_draft_cart_rejects_unconfirmed_intent(client, db_session):
    customer = _make_customer(db_session, saved_address={"line1": "x"})
    intent = _make_intent(db_session, customer, status="draft")
    product = _make_product(db_session)

    response = client.post(
        "/api/cart",
        json={"intent_mandate_id": str(intent.id), "items": [{"product_id": str(product.id), "quantity": 1}]},
    )

    assert response.status_code == 400
    assert "confirmed" in response.json()["detail"]


def test_draft_cart_rejects_unknown_intent(client):
    response = client.post(
        "/api/cart", json={"intent_mandate_id": str(uuid.uuid4()), "items": []}
    )
    assert response.status_code == 404


def test_draft_cart_rejects_unknown_product(client, db_session):
    customer = _make_customer(db_session, saved_address={"line1": "x"})
    intent = _make_intent(db_session, customer)

    response = client.post(
        "/api/cart",
        json={"intent_mandate_id": str(intent.id), "items": [{"product_id": str(uuid.uuid4()), "quantity": 1}]},
    )

    assert response.status_code == 404


def test_cart_references_correct_intent_mandate(client, db_session):
    customer = _make_customer(db_session, saved_address={"line1": "x"})
    intent = _make_intent(db_session, customer)
    product = _make_product(db_session)

    response = client.post(
        "/api/cart",
        json={"intent_mandate_id": str(intent.id), "items": [{"product_id": str(product.id), "quantity": 1}]},
    )

    assert response.json()["intent_mandate_id"] == str(intent.id)


def test_confirm_cart_signs_and_transitions(client, db_session):
    customer = _make_customer(db_session, saved_address={"line1": "x"})
    intent = _make_intent(db_session, customer)
    product = _make_product(db_session)
    draft = client.post(
        "/api/cart",
        json={"intent_mandate_id": str(intent.id), "items": [{"product_id": str(product.id), "quantity": 1}]},
    ).json()

    response = client.post(f"/api/cart/{draft['id']}/confirm")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "confirmed"
    assert body["confirmed_at"] is not None
    claims = verify_mandate(body["signature"])
    assert claims["mandate_type"] == "cart"
    assert claims["mandate_id"] == draft["id"]


def test_confirm_cart_exceeding_budget_rejected(client, db_session):
    customer = _make_customer(db_session, saved_address={"line1": "x"})
    intent = _make_intent(db_session, customer, budget_paise=10000)  # ₹100
    product = _make_product(db_session, price=49900)  # ₹499, alone exceeds budget + shipping
    draft = client.post(
        "/api/cart",
        json={"intent_mandate_id": str(intent.id), "items": [{"product_id": str(product.id), "quantity": 1}]},
    ).json()

    response = client.post(f"/api/cart/{draft['id']}/confirm")

    assert response.status_code == 400
    assert "exceeds intent budget" in response.json()["detail"]


def test_confirm_cart_within_budget_succeeds(client, db_session):
    customer = _make_customer(db_session, saved_address={"line1": "x"})
    intent = _make_intent(db_session, customer, budget_paise=1_000_000)  # ₹10,000
    product = _make_product(db_session, price=49900)
    draft = client.post(
        "/api/cart",
        json={"intent_mandate_id": str(intent.id), "items": [{"product_id": str(product.id), "quantity": 1}]},
    ).json()

    response = client.post(f"/api/cart/{draft['id']}/confirm")

    assert response.status_code == 200


def test_confirm_cart_twice_rejected(client, db_session):
    customer = _make_customer(db_session, saved_address={"line1": "x"})
    intent = _make_intent(db_session, customer)
    product = _make_product(db_session)
    draft = client.post(
        "/api/cart",
        json={"intent_mandate_id": str(intent.id), "items": [{"product_id": str(product.id), "quantity": 1}]},
    ).json()
    client.post(f"/api/cart/{draft['id']}/confirm")

    response = client.post(f"/api/cart/{draft['id']}/confirm")

    assert response.status_code == 400


def test_confirm_cart_nonexistent_returns_404(client):
    response = client.post(f"/api/cart/{uuid.uuid4()}/confirm")
    assert response.status_code == 404


def test_get_cart_nonexistent_returns_404(client):
    response = client.get(f"/api/cart/{uuid.uuid4()}")
    assert response.status_code == 404
