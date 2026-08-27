def _register(client, email):
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "hunter2", "role": "customer", "name": "Someone"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_get_profile_returns_the_registered_name(client):
    headers = _register(client, "profile1@example.com")

    response = client.get("/api/me/profile", headers=headers)

    assert response.status_code == 200
    assert response.json()["name"] == "Someone"


def test_patch_profile_updates_name_and_contact(client):
    headers = _register(client, "profile2@example.com")

    response = client.patch("/api/me/profile", json={"name": "New Name", "contact": "555-1234"}, headers=headers)

    assert response.status_code == 200
    assert response.json()["name"] == "New Name"
    assert response.json()["contact"] == "555-1234"


def test_profile_requires_authentication(client):
    response = client.get("/api/me/profile")
    assert response.status_code == 401


def test_add_and_list_addresses(client):
    headers = _register(client, "addr1@example.com")

    create = client.post("/api/me/addresses", json={"line1": "1 Main St", "city": "Pune"}, headers=headers)
    assert create.status_code == 200
    assert create.json()["is_default"] is True

    listing = client.get("/api/me/addresses", headers=headers)
    assert listing.status_code == 200
    assert len(listing.json()) == 1
    assert listing.json()[0]["line1"] == "1 Main St"


def test_second_address_is_not_default(client):
    headers = _register(client, "addr2@example.com")

    client.post("/api/me/addresses", json={"line1": "1 Main St"}, headers=headers)
    second = client.post("/api/me/addresses", json={"line1": "2 Side St"}, headers=headers)

    assert second.json()["is_default"] is False


def test_patch_address_can_set_default(client):
    headers = _register(client, "addr3@example.com")

    client.post("/api/me/addresses", json={"line1": "1 Main St"}, headers=headers)
    second = client.post("/api/me/addresses", json={"line1": "2 Side St"}, headers=headers)

    response = client.patch(
        f"/api/me/addresses/{second.json()['id']}", json={"is_default": True}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["is_default"] is True


def test_delete_address(client):
    headers = _register(client, "addr4@example.com")

    created = client.post("/api/me/addresses", json={"line1": "1 Main St"}, headers=headers)
    address_id = created.json()["id"]

    response = client.delete(f"/api/me/addresses/{address_id}", headers=headers)
    assert response.status_code == 204

    listing = client.get("/api/me/addresses", headers=headers)
    assert listing.json() == []


def test_cannot_edit_another_customers_address(client):
    headers_a = _register(client, "addr-a@example.com")
    headers_b = _register(client, "addr-b@example.com")

    created = client.post("/api/me/addresses", json={"line1": "1 Main St"}, headers=headers_a)
    address_id = created.json()["id"]

    response = client.patch(f"/api/me/addresses/{address_id}", json={"city": "Nope"}, headers=headers_b)
    assert response.status_code == 404


def test_cannot_delete_another_customers_address(client):
    headers_a = _register(client, "addr-c@example.com")
    headers_b = _register(client, "addr-d@example.com")

    created = client.post("/api/me/addresses", json={"line1": "1 Main St"}, headers=headers_a)
    address_id = created.json()["id"]

    response = client.delete(f"/api/me/addresses/{address_id}", headers=headers_b)
    assert response.status_code == 404


def test_addresses_rejects_a_merchant_token(client):
    register = client.post(
        "/api/auth/register",
        json={
            "email": "shop-addr@example.com",
            "password": "hunter2",
            "role": "merchant",
            "name": "Owner",
            "merchant_name": "Shop",
        },
    )
    token = register.json()["access_token"]

    response = client.get("/api/me/addresses", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403
