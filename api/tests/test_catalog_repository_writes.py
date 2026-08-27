import uuid

import pytest

from app.models import Merchant, PriceHistory, Product
from app.repositories.catalog import SqlAlchemyCatalogRepository


@pytest.fixture()
def merchant(db_session):
    m = Merchant(name="Test Merchant")
    db_session.add(m)
    db_session.flush()
    return m


def test_create_product_seeds_price_history(db_session, merchant):
    repo = SqlAlchemyCatalogRepository(db_session)

    product = repo.create_product(
        merchant_id=merchant.id, name="Phone Case", description="A case", category="accessories", price=999, stock=10
    )

    assert product.merchant_id == merchant.id
    assert product.tags == []
    history = db_session.query(PriceHistory).filter(PriceHistory.product_id == product.id).all()
    assert len(history) == 1
    assert history[0].price == 999


def test_create_product_stores_tags(db_session, merchant):
    repo = SqlAlchemyCatalogRepository(db_session)

    product = repo.create_product(
        merchant_id=merchant.id,
        name="Phone Case",
        description="A case",
        category="accessories",
        price=999,
        stock=10,
        tags=["phone", "case"],
    )

    assert product.tags == ["phone", "case"]


def test_update_product_changes_fields_without_touching_price_history(db_session, merchant):
    repo = SqlAlchemyCatalogRepository(db_session)
    product = repo.create_product(
        merchant_id=merchant.id, name="Phone Case", description=None, category=None, price=999, stock=10
    )

    updated = repo.update_product(product.id, description="Updated description")

    assert updated.description == "Updated description"
    assert db_session.query(PriceHistory).filter(PriceHistory.product_id == product.id).count() == 1


def test_update_product_price_appends_price_history(db_session, merchant):
    repo = SqlAlchemyCatalogRepository(db_session)
    product = repo.create_product(
        merchant_id=merchant.id, name="Phone Case", description=None, category=None, price=999, stock=10
    )

    updated = repo.update_product(product.id, price=1299)

    assert updated.price == 1299
    history = (
        db_session.query(PriceHistory)
        .filter(PriceHistory.product_id == product.id)
        .order_by(PriceHistory.changed_at)
        .all()
    )
    assert [h.price for h in history] == [999, 1299]


def test_update_product_same_price_does_not_append_history(db_session, merchant):
    repo = SqlAlchemyCatalogRepository(db_session)
    product = repo.create_product(
        merchant_id=merchant.id, name="Phone Case", description=None, category=None, price=999, stock=10
    )

    repo.update_product(product.id, price=999)

    assert db_session.query(PriceHistory).filter(PriceHistory.product_id == product.id).count() == 1


def test_update_product_raises_for_unknown_id(db_session, merchant):
    repo = SqlAlchemyCatalogRepository(db_session)

    with pytest.raises(LookupError):
        repo.update_product(uuid.uuid4(), name="x")


def test_delete_product_removes_it_and_its_price_history(db_session, merchant):
    repo = SqlAlchemyCatalogRepository(db_session)
    product = repo.create_product(
        merchant_id=merchant.id, name="Phone Case", description=None, category=None, price=999, stock=10
    )

    repo.delete_product(product.id)

    assert db_session.get(Product, product.id) is None
    assert db_session.query(PriceHistory).filter(PriceHistory.product_id == product.id).count() == 0


def test_delete_product_raises_for_unknown_id(db_session, merchant):
    repo = SqlAlchemyCatalogRepository(db_session)

    with pytest.raises(LookupError):
        repo.delete_product(uuid.uuid4())
