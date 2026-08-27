from app.routers import merchant as merchant_router


def _register_merchant(client, email, merchant_name="Shop"):
    response = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "hunter2",
            "role": "merchant",
            "name": "Owner",
            "merchant_name": merchant_name,
        },
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_product_generates_tags(monkeypatch, client):
    monkeypatch.setattr(merchant_router, "generate_tags_for_product", lambda *a, **k: ["phone", "case"])
    headers = _register_merchant(client, "shop1@example.com")

    response = client.post(
        "/api/merchant/products",
        json={"name": "Phone Case", "description": "A case", "category": "accessories", "price": 999, "stock": 10},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tags"] == ["phone", "case"]
    assert body["name"] == "Phone Case"


def test_create_product_degrades_to_no_tags_on_generation_failure(monkeypatch, client):
    monkeypatch.setattr(merchant_router, "generate_tags_for_product", lambda *a, **k: [])
    headers = _register_merchant(client, "shop2@example.com")

    response = client.post(
        "/api/merchant/products",
        json={"name": "Phone Case", "price": 999},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["tags"] == []


def test_list_my_products_only_returns_own_merchants_products(monkeypatch, client):
    monkeypatch.setattr(merchant_router, "generate_tags_for_product", lambda *a, **k: [])
    headers_a = _register_merchant(client, "shop-a@example.com", "Shop A")
    headers_b = _register_merchant(client, "shop-b@example.com", "Shop B")

    client.post("/api/merchant/products", json={"name": "A's Product", "price": 100}, headers=headers_a)
    client.post("/api/merchant/products", json={"name": "B's Product", "price": 200}, headers=headers_b)

    response = client.get("/api/merchant/products", headers=headers_a)

    assert response.status_code == 200
    names = [p["name"] for p in response.json()]
    assert names == ["A's Product"]


def test_update_product_regenerates_tags_when_description_changes(monkeypatch, client):
    calls = []

    def fake_generate(name, description, category):
        calls.append((name, description, category))
        return ["regenerated"]

    monkeypatch.setattr(merchant_router, "generate_tags_for_product", fake_generate)
    headers = _register_merchant(client, "shop3@example.com")

    created = client.post(
        "/api/merchant/products", json={"name": "Phone Case", "description": "old", "price": 999}, headers=headers
    )
    product_id = created.json()["id"]

    response = client.patch(
        f"/api/merchant/products/{product_id}", json={"description": "new description"}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["tags"] == ["regenerated"]
    assert calls[-1] == ("Phone Case", "new description", None)


def test_update_product_does_not_regenerate_tags_when_description_unchanged(monkeypatch, client):
    call_count = 0

    def fake_generate(*a, **k):
        nonlocal call_count
        call_count += 1
        return ["tag"]

    monkeypatch.setattr(merchant_router, "generate_tags_for_product", fake_generate)
    headers = _register_merchant(client, "shop4@example.com")

    created = client.post(
        "/api/merchant/products", json={"name": "Phone Case", "description": "d", "price": 999}, headers=headers
    )
    assert call_count == 1
    product_id = created.json()["id"]

    response = client.patch(f"/api/merchant/products/{product_id}", json={"price": 1099}, headers=headers)

    assert response.status_code == 200
    assert response.json()["price"] == 1099
    assert call_count == 1  # unchanged — description wasn't touched


def test_cannot_update_another_merchants_product(monkeypatch, client):
    monkeypatch.setattr(merchant_router, "generate_tags_for_product", lambda *a, **k: [])
    headers_a = _register_merchant(client, "shop-c@example.com", "Shop C")
    headers_b = _register_merchant(client, "shop-d@example.com", "Shop D")

    created = client.post("/api/merchant/products", json={"name": "A's Product", "price": 100}, headers=headers_a)
    product_id = created.json()["id"]

    response = client.patch(f"/api/merchant/products/{product_id}", json={"price": 1}, headers=headers_b)
    assert response.status_code == 404


def test_cannot_delete_another_merchants_product(monkeypatch, client):
    monkeypatch.setattr(merchant_router, "generate_tags_for_product", lambda *a, **k: [])
    headers_a = _register_merchant(client, "shop-e@example.com", "Shop E")
    headers_b = _register_merchant(client, "shop-f@example.com", "Shop F")

    created = client.post("/api/merchant/products", json={"name": "A's Product", "price": 100}, headers=headers_a)
    product_id = created.json()["id"]

    response = client.delete(f"/api/merchant/products/{product_id}", headers=headers_b)
    assert response.status_code == 404


def test_delete_my_own_product(monkeypatch, client):
    monkeypatch.setattr(merchant_router, "generate_tags_for_product", lambda *a, **k: [])
    headers = _register_merchant(client, "shop5@example.com")

    created = client.post("/api/merchant/products", json={"name": "Product", "price": 100}, headers=headers)
    product_id = created.json()["id"]

    response = client.delete(f"/api/merchant/products/{product_id}", headers=headers)
    assert response.status_code == 204

    listing = client.get("/api/merchant/products", headers=headers)
    assert listing.json() == []


def test_merchant_products_requires_authentication(client):
    response = client.get("/api/merchant/products")
    assert response.status_code == 401


def test_merchant_products_rejects_a_customer_token(client):
    register = client.post(
        "/api/auth/register",
        json={"email": "cust-merch@example.com", "password": "hunter2", "role": "customer", "name": "Cust"},
    )
    token = register.json()["access_token"]

    response = client.get("/api/merchant/products", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_new_product_is_immediately_searchable(monkeypatch, client):
    monkeypatch.setattr(merchant_router, "generate_tags_for_product", lambda *a, **k: [])
    headers = _register_merchant(client, "shop6@example.com")

    client.post(
        "/api/merchant/products",
        json={"name": "Ultra Rare Gizmo", "description": "one of a kind", "price": 500},
        headers=headers,
    )

    response = client.get("/api/catalog/search", params={"q": "Ultra Rare Gizmo"})

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "Ultra Rare Gizmo"
