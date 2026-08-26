import uuid

from app.models import Merchant, Product


def _make_merchant_with_products(db_session, products: list[dict]) -> Merchant:
    merchant = Merchant(name="Test Merchant")
    db_session.add(merchant)
    db_session.flush()
    for p in products:
        db_session.add(Product(merchant_id=merchant.id, **p))
    db_session.commit()
    return merchant


def test_list_products(client, db_session):
    _make_merchant_with_products(
        db_session,
        [
            {"name": "USB-C Cable", "description": "1m cable", "price": 29900, "stock": 10},
            {"name": "Power Bank", "description": "10000mAh", "price": 149900, "stock": 5},
        ],
    )

    response = client.get("/api/catalog/products")
    assert response.status_code == 200
    names = {p["name"] for p in response.json()}
    assert names == {"USB-C Cable", "Power Bank"}


def test_list_products_no_merchant_seeded(client):
    response = client.get("/api/catalog/products")
    assert response.status_code == 404


def test_get_product(client, db_session):
    merchant = _make_merchant_with_products(
        db_session, [{"name": "Wireless Earbuds", "description": None, "price": 249900, "stock": 3}]
    )
    product = db_session.query(Product).filter(Product.merchant_id == merchant.id).one()

    response = client.get(f"/api/catalog/products/{product.id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Wireless Earbuds"


def test_get_product_not_found(client):
    response = client.get(f"/api/catalog/products/{uuid.uuid4()}")
    assert response.status_code == 404


def test_search_matches_name_and_description(client, db_session):
    _make_merchant_with_products(
        db_session,
        [
            {"name": "20W Fast Charger", "description": "USB-C wall charger", "price": 89900, "stock": 10},
            {"name": "Bluetooth Speaker", "description": "Charges via USB-C", "price": 179900, "stock": 4},
            {"name": "Phone Case", "description": "Clear slim case", "price": 49900, "stock": 20},
        ],
    )

    response = client.get("/api/catalog/search", params={"q": "charg"})
    assert response.status_code == 200
    names = {p["name"] for p in response.json()}
    assert names == {"20W Fast Charger", "Bluetooth Speaker"}


def test_search_no_match_returns_empty(client, db_session):
    _make_merchant_with_products(db_session, [{"name": "Phone Case", "description": None, "price": 49900, "stock": 20}])

    response = client.get("/api/catalog/search", params={"q": "nonexistent"})
    assert response.status_code == 200
    assert response.json() == []


def test_search_includes_merchant_name(client, db_session):
    _make_merchant_with_products(db_session, [{"name": "USB-C Cable", "description": None, "price": 29900, "stock": 10}])

    response = client.get("/api/catalog/search", params={"q": "cable"})

    assert response.json()[0]["merchant_name"] == "Test Merchant"


def test_search_spans_multiple_merchants(client, db_session):
    """P3.3: search has never been merchant-scoped — with more than one
    merchant seeded, the same product query should surface all of them."""
    merchant_a = Merchant(name="Merchant A")
    merchant_b = Merchant(name="Merchant B")
    db_session.add_all([merchant_a, merchant_b])
    db_session.flush()
    db_session.add(Product(merchant_id=merchant_a.id, name="Wireless Earbuds Pro", description=None, price=219900, stock=10))
    db_session.add(Product(merchant_id=merchant_b.id, name="Wireless Earbuds Pro", description=None, price=279900, stock=10))
    db_session.commit()

    response = client.get("/api/catalog/search", params={"q": "earbuds"})

    results = response.json()
    assert len(results) == 2
    merchants_and_prices = {(r["merchant_name"], r["price"]) for r in results}
    assert merchants_and_prices == {("Merchant A", 219900), ("Merchant B", 279900)}
