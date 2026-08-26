import uuid
from datetime import UTC, datetime

import pytest

from app.models import CartMandate, Customer, IntentMandate, PaymentMandate
from app.services.audit import (
    get_transaction_audit_trail,
    list_recent_transactions,
    record_transition,
)


def _customer(db_session) -> Customer:
    customer = Customer(name="t")
    db_session.add(customer)
    db_session.flush()
    return customer


def _full_transaction(db_session):
    """intent -> cart -> two payments (a failed attempt, then a retry),
    with audit rows recorded exactly like the real services would."""
    customer = _customer(db_session)
    intent = IntentMandate(
        customer_id=customer.id,
        raw_text="wireless earbuds under 3000",
        structured_json={},
        status="draft",
    )
    db_session.add(intent)
    db_session.flush()
    record_transition(db_session, "intent", intent.id, None, "draft", "customer", "h1")

    intent.status = "confirmed"
    intent.confirmed_at = datetime.now(UTC)
    intent.signature = "s"
    record_transition(db_session, "intent", intent.id, "draft", "confirmed", "customer", "h2")

    cart = CartMandate(
        intent_mandate_id=intent.id,
        items=[],
        total_amount=254800,
        shipping_address={},
        status="confirmed",
        signature="s",
        confirmed_at=datetime.now(UTC),
    )
    db_session.add(cart)
    db_session.flush()
    record_transition(db_session, "cart", cart.id, "draft", "confirmed", "customer", "h3")

    failed_payment = PaymentMandate(cart_mandate_id=cart.id, razorpay_ref="order_1", amount=254800, status="failed")
    db_session.add(failed_payment)
    db_session.flush()
    record_transition(db_session, "payment", failed_payment.id, None, "pending", "system", "h4")
    record_transition(db_session, "payment", failed_payment.id, "pending", "failed", "system", "h5")

    retried_payment = PaymentMandate(
        cart_mandate_id=cart.id, razorpay_ref="order_2", amount=254800, status="executed"
    )
    db_session.add(retried_payment)
    db_session.flush()
    record_transition(db_session, "payment", retried_payment.id, None, "pending", "system", "h6")
    record_transition(db_session, "payment", retried_payment.id, "pending", "executed", "system", "h7")

    db_session.commit()
    return intent, cart, failed_payment, retried_payment


def test_get_transaction_audit_trail_collects_full_chain(db_session):
    intent, cart, failed_payment, retried_payment = _full_transaction(db_session)

    trail = get_transaction_audit_trail(db_session, intent.id)

    assert trail.intent.id == intent.id
    assert [c.id for c in trail.carts] == [cart.id]
    assert {p.id for p in trail.payments} == {failed_payment.id, retried_payment.id}
    assert len(trail.entries) == 7
    hashes_in_order = [e.payload_hash for e in trail.entries]
    assert hashes_in_order == ["h1", "h2", "h3", "h4", "h5", "h6", "h7"]


def test_get_transaction_audit_trail_ignores_other_transactions(db_session):
    intent, *_ = _full_transaction(db_session)
    other_customer = _customer(db_session)
    other_intent = IntentMandate(customer_id=other_customer.id, raw_text="x", structured_json={}, status="draft")
    db_session.add(other_intent)
    db_session.flush()
    record_transition(db_session, "intent", other_intent.id, None, "draft", "customer", "unrelated")
    db_session.commit()

    trail = get_transaction_audit_trail(db_session, intent.id)

    assert "unrelated" not in [e.payload_hash for e in trail.entries]


def test_get_transaction_audit_trail_unknown_intent_raises(db_session):
    with pytest.raises(LookupError):
        get_transaction_audit_trail(db_session, uuid.uuid4())


def test_get_transaction_audit_trail_intent_with_no_cart_yet(db_session):
    customer = _customer(db_session)
    intent = IntentMandate(customer_id=customer.id, raw_text="x", structured_json={}, status="draft")
    db_session.add(intent)
    db_session.flush()
    record_transition(db_session, "intent", intent.id, None, "draft", "customer", "only-one")
    db_session.commit()

    trail = get_transaction_audit_trail(db_session, intent.id)

    assert trail.carts == []
    assert trail.payments == []
    assert len(trail.entries) == 1


def test_list_recent_transactions_orders_newest_first(db_session):
    customer = _customer(db_session)
    older = IntentMandate(customer_id=customer.id, raw_text="older", structured_json={}, status="draft")
    db_session.add(older)
    db_session.flush()
    newer = IntentMandate(customer_id=customer.id, raw_text="newer", structured_json={}, status="draft")
    db_session.add(newer)
    db_session.commit()

    results = list_recent_transactions(db_session, limit=10)

    ids = [i.id for i in results]
    assert ids.index(newer.id) < ids.index(older.id)


def test_list_recent_transactions_respects_limit(db_session):
    customer = _customer(db_session)
    for i in range(5):
        db_session.add(IntentMandate(customer_id=customer.id, raw_text=str(i), structured_json={}, status="draft"))
    db_session.commit()

    assert len(list_recent_transactions(db_session, limit=2)) == 2


def test_api_transaction_json_endpoint(client, db_session):
    intent, cart, failed_payment, retried_payment = _full_transaction(db_session)

    response = client.get(f"/api/audit/transactions/{intent.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["intent_id"] == str(intent.id)
    assert body["intent_status"] == "confirmed"
    assert set(body["cart_ids"]) == {str(cart.id)}
    assert set(body["payment_ids"]) == {str(failed_payment.id), str(retried_payment.id)}
    assert len(body["entries"]) == 7


def test_api_transaction_json_endpoint_404_for_unknown_intent(client):
    response = client.get(f"/api/audit/transactions/{uuid.uuid4()}")
    assert response.status_code == 404


def test_api_list_transactions_endpoint(client, db_session):
    intent, *_ = _full_transaction(db_session)

    response = client.get("/api/audit/transactions")

    assert response.status_code == 200
    ids = [t["intent_id"] for t in response.json()]
    assert str(intent.id) in ids


def test_html_index_lists_transaction_and_links_to_detail(client, db_session):
    intent, *_ = _full_transaction(db_session)

    response = client.get("/audit")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert str(intent.id) in response.text
    assert f"/audit/{intent.id}" in response.text


def test_html_detail_shows_full_chain(client, db_session):
    intent, cart, failed_payment, retried_payment = _full_transaction(db_session)

    response = client.get(f"/audit/{intent.id}")

    assert response.status_code == 200
    text = response.text
    assert str(cart.id) in text
    assert str(failed_payment.id) in text
    assert str(retried_payment.id) in text
    assert "failed" in text
    assert "executed" in text


def test_html_detail_404_for_unknown_intent(client):
    response = client.get(f"/audit/{uuid.uuid4()}")
    assert response.status_code == 404


def test_html_escapes_raw_text_to_prevent_xss(client, db_session):
    customer = _customer(db_session)
    intent = IntentMandate(
        customer_id=customer.id,
        raw_text="<script>alert(1)</script>",
        structured_json={},
        status="draft",
    )
    db_session.add(intent)
    db_session.commit()
    record_transition(db_session, "intent", intent.id, None, "draft", "customer", "h")
    db_session.commit()

    response = client.get("/audit")

    assert "<script>alert(1)</script>" not in response.text
    assert "&lt;script&gt;" in response.text
