import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

import mcp_server.auth as mcp_auth_module
from app.config import settings
from app.models import Customer, Merchant, User
from app.services.auth_tokens import create_access_token
from app.services.password import hash_password


class _NonClosingSession:
    """Wraps the shared, rolled-back test db_session so the middleware's own
    `db.close()` doesn't tear down a session other fixtures still need."""

    def __init__(self, session):
        self._session = session

    def get(self, *args, **kwargs):
        return self._session.get(*args, **kwargs)

    def close(self):
        pass


@pytest.fixture(autouse=True)
def _use_test_db(monkeypatch, db_session):
    monkeypatch.setattr(mcp_auth_module, "SessionLocal", lambda: _NonClosingSession(db_session))


async def _echo_state(request):
    return JSONResponse({"customer_id": getattr(request.state, "customer_id", None)})


def _client() -> TestClient:
    inner = Starlette(routes=[Route("/mcp", _echo_state, methods=["POST"])])
    app = mcp_auth_module.BearerAuthMiddleware(inner)
    return TestClient(app)


def _customer_user(db_session) -> User:
    customer = Customer(name="Test")
    db_session.add(customer)
    db_session.flush()
    user = User(email="c@example.com", password_hash=hash_password("x"), role="customer", customer_id=customer.id)
    db_session.add(user)
    db_session.commit()
    return user


def test_missing_authorization_header_is_rejected():
    response = _client().post("/mcp", json={})
    assert response.status_code == 401


def test_malformed_bearer_token_is_rejected():
    response = _client().post("/mcp", json={}, headers={"Authorization": "Bearer not-a-real-jwt"})
    assert response.status_code == 401


def test_expired_token_is_rejected(db_session):
    user = _customer_user(db_session)
    now = datetime.now(UTC)
    expired = jwt.encode(
        {"sub": str(user.id), "role": "customer", "iat": now - timedelta(hours=2), "exp": now - timedelta(hours=1)},
        settings.auth_jwt_secret,
        algorithm=settings.auth_jwt_algorithm,
    )
    response = _client().post("/mcp", json={}, headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401


def test_token_for_nonexistent_user_is_rejected():
    token = create_access_token(uuid.uuid4(), "customer")
    response = _client().post("/mcp", json={}, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_merchant_token_is_rejected_this_server_is_customer_only(db_session):
    merchant = Merchant(name="M")
    db_session.add(merchant)
    db_session.flush()
    user = User(email="m@example.com", password_hash=hash_password("x"), role="merchant", merchant_id=merchant.id)
    db_session.add(user)
    db_session.commit()
    token = create_access_token(user.id, user.role)

    response = _client().post("/mcp", json={}, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


def test_admin_token_is_rejected_this_server_is_customer_only(db_session):
    admin = User(email="a@example.com", password_hash=hash_password("x"), role="admin")
    db_session.add(admin)
    db_session.commit()
    token = create_access_token(admin.id, admin.role)

    response = _client().post("/mcp", json={}, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


def test_valid_customer_token_is_accepted_and_scoped(db_session):
    user = _customer_user(db_session)
    token = create_access_token(user.id, user.role)

    response = _client().post("/mcp", json={}, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["customer_id"] == str(user.customer_id)


def _client_with_metadata() -> TestClient:
    inner = Starlette(routes=[Route("/mcp", _echo_state, methods=["POST"])])
    app = mcp_auth_module.ProtectedResourceMetadataMiddleware(
        mcp_auth_module.BearerAuthMiddleware(inner),
        resource="http://mcp.example.com/mcp",
        authorization_server="http://backend.example.com",
    )
    return TestClient(app)


def test_protected_resource_metadata_is_reachable_without_a_token():
    response = _client_with_metadata().get(mcp_auth_module.PROTECTED_RESOURCE_METADATA_PATH)

    assert response.status_code == 200
    body = response.json()
    assert body["resource"] == "http://mcp.example.com/mcp"
    assert body["authorization_servers"] == ["http://backend.example.com"]


def test_protected_resource_metadata_does_not_shadow_the_mcp_route(db_session):
    """Only the exact metadata path is intercepted — /mcp itself still goes
    through BearerAuthMiddleware exactly as before."""
    response = _client_with_metadata().post("/mcp", json={})

    assert response.status_code == 401
