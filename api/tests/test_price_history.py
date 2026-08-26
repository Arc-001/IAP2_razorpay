import uuid

import pytest

from app.models import Merchant, PriceHistory, Product
from app.services.price_history import price_has_risen_significantly, record_price_change


def _make_product(db_session, price=10000) -> Product:
    merchant = Merchant(name="M")
    db_session.add(merchant)
    db_session.flush()
    product = Product(merchant_id=merchant.id, name="Widget", description=None, price=price, stock=10)
    db_session.add(product)
    db_session.commit()
    return product


def test_no_history_means_no_rise_detected(db_session):
    product = _make_product(db_session)

    risen, previous, current = price_has_risen_significantly(db_session, product.id)

    assert risen is False
    assert previous is None
    assert current == product.price


def test_single_history_row_means_no_comparison_possible(db_session):
    product = _make_product(db_session)
    db_session.add(PriceHistory(product_id=product.id, price=product.price))
    db_session.commit()

    risen, previous, _ = price_has_risen_significantly(db_session, product.id)

    assert risen is False
    assert previous is None


def test_price_rise_over_threshold_is_detected(db_session):
    product = _make_product(db_session, price=10000)
    db_session.add(PriceHistory(product_id=product.id, price=10000))
    db_session.commit()

    record_price_change(db_session, product.id, 12000)  # +20%

    risen, previous, current = price_has_risen_significantly(db_session, product.id)
    assert risen is True
    assert previous == 10000
    assert current == 12000


def test_price_rise_within_threshold_is_not_flagged(db_session):
    product = _make_product(db_session, price=10000)
    db_session.add(PriceHistory(product_id=product.id, price=10000))
    db_session.commit()

    record_price_change(db_session, product.id, 10500)  # +5%

    risen, _, _ = price_has_risen_significantly(db_session, product.id)
    assert risen is False


def test_price_drop_is_not_flagged(db_session):
    product = _make_product(db_session, price=10000)
    db_session.add(PriceHistory(product_id=product.id, price=10000))
    db_session.commit()

    record_price_change(db_session, product.id, 8000)

    risen, _, _ = price_has_risen_significantly(db_session, product.id)
    assert risen is False


def test_record_price_change_unknown_product_raises_lookup_error(db_session):
    with pytest.raises(LookupError):
        record_price_change(db_session, uuid.uuid4(), 100)


def test_price_has_risen_unknown_product_raises_lookup_error(db_session):
    with pytest.raises(LookupError):
        price_has_risen_significantly(db_session, uuid.uuid4())
