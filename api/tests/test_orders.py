from datetime import UTC, datetime

from app.models import CartMandate, Customer, IntentMandate, PaymentMandate
from app.services.orders import list_customer_orders


def _make_intent(db_session, customer, product_query="wireless earbuds") -> IntentMandate:
    intent = IntentMandate(
        customer_id=customer.id,
        raw_text=f"I want {product_query}",
        structured_json={"product_query": product_query, "quantity": 1, "budget_paise": None, "constraints": []},
        status="confirmed",
        signature="fake-sig",
        confirmed_at=datetime.now(UTC),
    )
    db_session.add(intent)
    db_session.flush()
    return intent


def test_list_customer_orders_only_returns_the_given_customers_intents(db_session):
    customer = Customer(name="A")
    other = Customer(name="B")
    db_session.add_all([customer, other])
    db_session.flush()

    _make_intent(db_session, customer)
    _make_intent(db_session, other)
    db_session.commit()

    orders = list_customer_orders(db_session, customer.id)

    assert len(orders) == 1
    assert orders[0].intent.customer_id == customer.id


def test_order_with_no_cart_yet_has_none_cart_and_payment(db_session):
    customer = Customer(name="A")
    db_session.add(customer)
    db_session.flush()
    _make_intent(db_session, customer)
    db_session.commit()

    orders = list_customer_orders(db_session, customer.id)

    assert orders[0].cart is None
    assert orders[0].payment is None


def test_order_picks_the_most_recent_cart_and_payment(db_session):
    customer = Customer(name="A")
    db_session.add(customer)
    db_session.flush()
    intent = _make_intent(db_session, customer)

    cart1 = CartMandate(intent_mandate_id=intent.id, items=[], total_amount=100, status="draft")
    db_session.add(cart1)
    db_session.flush()
    cart2 = CartMandate(intent_mandate_id=intent.id, items=[], total_amount=200, status="confirmed")
    db_session.add(cart2)
    db_session.flush()

    payment = PaymentMandate(cart_mandate_id=cart2.id, amount=200, status="executed")
    db_session.add(payment)
    db_session.commit()

    orders = list_customer_orders(db_session, customer.id)

    assert orders[0].cart.id == cart2.id
    assert orders[0].payment.id == payment.id
    assert orders[0].payment.status == "executed"
