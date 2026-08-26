import uuid
from datetime import UTC, datetime

import pytest

from app.models import CartMandate, Customer, IntentMandate, PaymentMandate
from app.orchestrator.state import AgentState, derive_state


def _customer(db_session) -> Customer:
    customer = Customer(name="t")
    db_session.add(customer)
    db_session.flush()
    return customer


def _confirmed_intent(db_session, customer) -> IntentMandate:
    intent = IntentMandate(
        customer_id=customer.id,
        raw_text="x",
        structured_json={},
        status="confirmed",
        signature="s",
        confirmed_at=datetime.now(UTC),
    )
    db_session.add(intent)
    db_session.flush()
    return intent


def _confirmed_cart(db_session, intent) -> CartMandate:
    cart = CartMandate(
        intent_mandate_id=intent.id,
        items=[],
        total_amount=100,
        shipping_address={},
        status="confirmed",
        signature="s",
        confirmed_at=datetime.now(UTC),
    )
    db_session.add(cart)
    db_session.flush()
    return cart


def test_no_ids_is_drafting_intent(db_session):
    assert derive_state(db_session, None, None, None) == AgentState.DRAFTING_INTENT


def test_draft_intent_is_awaiting_intent_ok(db_session):
    customer = _customer(db_session)
    intent = IntentMandate(customer_id=customer.id, raw_text="x", structured_json={}, status="draft")
    db_session.add(intent)
    db_session.commit()

    assert derive_state(db_session, intent.id, None, None) == AgentState.AWAITING_INTENT_OK


def test_confirmed_intent_no_cart_is_building_cart(db_session):
    customer = _customer(db_session)
    intent = _confirmed_intent(db_session, customer)
    db_session.commit()

    assert derive_state(db_session, intent.id, None, None) == AgentState.BUILDING_CART


def test_draft_cart_is_awaiting_cart_ok(db_session):
    customer = _customer(db_session)
    intent = _confirmed_intent(db_session, customer)
    cart = CartMandate(intent_mandate_id=intent.id, items=[], total_amount=100, shipping_address={}, status="draft")
    db_session.add(cart)
    db_session.commit()

    assert derive_state(db_session, intent.id, cart.id, None) == AgentState.AWAITING_CART_OK


def test_confirmed_cart_no_payment_is_executing_payment(db_session):
    customer = _customer(db_session)
    intent = _confirmed_intent(db_session, customer)
    cart = _confirmed_cart(db_session, intent)
    db_session.commit()

    assert derive_state(db_session, intent.id, cart.id, None) == AgentState.EXECUTING_PAYMENT


def test_pending_payment_is_executing_payment(db_session):
    customer = _customer(db_session)
    intent = _confirmed_intent(db_session, customer)
    cart = _confirmed_cart(db_session, intent)
    payment = PaymentMandate(cart_mandate_id=cart.id, amount=100, status="pending")
    db_session.add(payment)
    db_session.commit()

    assert derive_state(db_session, intent.id, cart.id, payment.id) == AgentState.EXECUTING_PAYMENT


@pytest.mark.parametrize("status", ["executed", "cancelled"])
def test_resolved_payment_is_terminal(db_session, status):
    customer = _customer(db_session)
    intent = _confirmed_intent(db_session, customer)
    cart = _confirmed_cart(db_session, intent)
    payment = PaymentMandate(cart_mandate_id=cart.id, amount=100, status=status)
    db_session.add(payment)
    db_session.commit()

    assert derive_state(db_session, intent.id, cart.id, payment.id) == AgentState.TERMINAL


def test_failed_payment_is_payment_failed_not_terminal(db_session):
    """A failed payment must not be a dead end (CLAUDE.md §8 step 10): the
    human gets offered retry or cancel, not silence."""
    customer = _customer(db_session)
    intent = _confirmed_intent(db_session, customer)
    cart = _confirmed_cart(db_session, intent)
    payment = PaymentMandate(cart_mandate_id=cart.id, amount=100, status="failed")
    db_session.add(payment)
    db_session.commit()

    assert derive_state(db_session, intent.id, cart.id, payment.id) == AgentState.PAYMENT_FAILED


def test_unknown_intent_id_raises_lookup_error(db_session):
    with pytest.raises(LookupError):
        derive_state(db_session, uuid.uuid4(), None, None)


def test_unknown_cart_id_raises_lookup_error(db_session):
    with pytest.raises(LookupError):
        derive_state(db_session, None, uuid.uuid4(), None)


def test_unknown_payment_id_raises_lookup_error(db_session):
    with pytest.raises(LookupError):
        derive_state(db_session, None, None, uuid.uuid4())
