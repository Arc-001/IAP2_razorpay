from app.models import Customer, Merchant, User


def test_register_customer_creates_user_and_customer_row(client, db_session):
    response = client.post(
        "/api/auth/register",
        json={"email": "alice@example.com", "password": "hunter2", "role": "customer", "name": "Alice"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["role"] == "customer"
    assert body["user"]["customer_id"] is not None
    assert body["user"]["merchant_id"] is None
    assert body["access_token"]

    customer = db_session.get(Customer, body["user"]["customer_id"])
    assert customer.name == "Alice"


def test_register_merchant_creates_user_and_merchant_row(client, db_session):
    response = client.post(
        "/api/auth/register",
        json={
            "email": "shop@example.com",
            "password": "hunter2",
            "role": "merchant",
            "name": "Shop Owner",
            "merchant_name": "Alice's Shop",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["merchant_id"] is not None

    merchant = db_session.get(Merchant, body["user"]["merchant_id"])
    assert merchant.name == "Alice's Shop"


def test_register_merchant_without_merchant_name_is_rejected(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "shop2@example.com", "password": "hunter2", "role": "merchant", "name": "Shop Owner"},
    )

    assert response.status_code == 400


def test_register_duplicate_email_is_rejected(client):
    payload = {"email": "dup@example.com", "password": "hunter2", "role": "customer", "name": "Dup"}
    first = client.post("/api/auth/register", json=payload)
    assert first.status_code == 200

    second = client.post("/api/auth/register", json=payload)
    assert second.status_code == 400


def test_login_with_correct_credentials_succeeds(client):
    client.post(
        "/api/auth/register",
        json={"email": "bob@example.com", "password": "correct-horse", "role": "customer", "name": "Bob"},
    )

    response = client.post("/api/auth/login", json={"email": "bob@example.com", "password": "correct-horse"})

    assert response.status_code == 200
    assert response.json()["access_token"]


def test_login_with_wrong_password_is_rejected(client):
    client.post(
        "/api/auth/register",
        json={"email": "carol@example.com", "password": "correct-horse", "role": "customer", "name": "Carol"},
    )

    response = client.post("/api/auth/login", json={"email": "carol@example.com", "password": "wrong"})

    assert response.status_code == 401


def test_login_with_unknown_email_is_rejected(client):
    response = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "x"})

    assert response.status_code == 401


def test_me_requires_a_bearer_token(client):
    response = client.get("/api/auth/me")

    assert response.status_code == 401


def test_me_rejects_garbage_token(client):
    response = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"})

    assert response.status_code == 401


def test_me_returns_the_authenticated_user(client):
    register = client.post(
        "/api/auth/register",
        json={"email": "dana@example.com", "password": "hunter2", "role": "customer", "name": "Dana"},
    )
    token = register.json()["access_token"]

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["email"] == "dana@example.com"


def test_require_role_rejects_a_role_not_in_the_allowed_set():
    from app.dependencies.auth import require_role

    check = require_role("admin")
    fake_customer = User(email="x@example.com", password_hash="x", role="customer")

    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        check(user=fake_customer)
    assert exc_info.value.status_code == 403


def test_require_role_allows_a_role_in_the_allowed_set():
    from app.dependencies.auth import require_role

    check = require_role("admin", "merchant")
    fake_merchant = User(email="x@example.com", password_hash="x", role="merchant")

    assert check(user=fake_merchant) is fake_merchant
