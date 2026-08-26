import uuid

from app.models import Merchant, Product
from app.services.upsell import suggest_upsell_candidates


def _merchant(db_session, name="M") -> Merchant:
    merchant = Merchant(name=name)
    db_session.add(merchant)
    db_session.flush()
    return merchant


def test_returns_empty_for_no_selected_products(db_session):
    assert suggest_upsell_candidates(db_session, []) == []


def test_returns_empty_when_selected_ids_dont_match_any_product(db_session):
    assert suggest_upsell_candidates(db_session, [uuid.uuid4()]) == []


def test_returns_other_same_merchant_products_excluding_selected(db_session):
    merchant = _merchant(db_session)
    selected = Product(merchant_id=merchant.id, name="Power Bank", description=None, price=100000, stock=5)
    other = Product(merchant_id=merchant.id, name="USB-C Cable", description=None, price=29900, stock=10)
    db_session.add_all([selected, other])
    db_session.commit()

    candidates = suggest_upsell_candidates(db_session, [selected.id])

    assert [c.id for c in candidates] == [other.id]


def test_excludes_products_from_other_merchants(db_session):
    merchant_a = _merchant(db_session, "A")
    merchant_b = _merchant(db_session, "B")
    selected = Product(merchant_id=merchant_a.id, name="Power Bank", description=None, price=100000, stock=5)
    unrelated = Product(merchant_id=merchant_b.id, name="Unrelated Item", description=None, price=5000, stock=5)
    db_session.add_all([selected, unrelated])
    db_session.commit()

    candidates = suggest_upsell_candidates(db_session, [selected.id])

    assert candidates == []


def test_respects_limit(db_session):
    merchant = _merchant(db_session)
    selected = Product(merchant_id=merchant.id, name="Main Item", description=None, price=100000, stock=5)
    db_session.add(selected)
    for i in range(5):
        db_session.add(Product(merchant_id=merchant.id, name=f"Addon {i}", description=None, price=1000, stock=5))
    db_session.commit()

    candidates = suggest_upsell_candidates(db_session, [selected.id], limit=2)

    assert len(candidates) == 2
