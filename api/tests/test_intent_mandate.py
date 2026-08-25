import uuid

import pytest

from app.models import Customer
from app.schemas.intent import IntentExtractionResponse
from app.services import intent_mandate
from app.services.mandate_signing import verify_mandate

FAKE_EXTRACTION = IntentExtractionResponse(
    raw_text="I want wireless earbuds under 3000 rupees",
    product_query="wireless earbuds",
    quantity=1,
    budget_paise=300000,
    constraints=[],
)


@pytest.fixture(autouse=True)
def mock_extraction(monkeypatch):
    monkeypatch.setattr(intent_mandate, "extract_intent", lambda raw_text: FAKE_EXTRACTION)


def test_draft_creates_unsigned_mandate_with_default_customer(client, db_session):
    response = client.post("/api/intent", json={"raw_text": FAKE_EXTRACTION.raw_text})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "draft"
    assert body["signature"] is None
    assert body["confirmed_at"] is None
    assert body["structured_json"]["product_query"] == "wireless earbuds"

    # Demo customer auto-created and reused
    assert db_session.query(Customer).count() == 1


def test_draft_with_explicit_customer_id(client, db_session):
    customer = Customer(name="Alice")
    db_session.add(customer)
    db_session.commit()

    response = client.post(
        "/api/intent", json={"raw_text": FAKE_EXTRACTION.raw_text, "customer_id": str(customer.id)}
    )

    assert response.status_code == 200
    assert response.json()["customer_id"] == str(customer.id)


def test_draft_with_unknown_customer_id_returns_404(client):
    response = client.post(
        "/api/intent", json={"raw_text": FAKE_EXTRACTION.raw_text, "customer_id": str(uuid.uuid4())}
    )
    assert response.status_code == 404


def test_confirm_signs_and_transitions_to_confirmed(client):
    draft = client.post("/api/intent", json={"raw_text": FAKE_EXTRACTION.raw_text}).json()

    response = client.post(f"/api/intent/{draft['id']}/confirm")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "confirmed"
    assert body["confirmed_at"] is not None
    claims = verify_mandate(body["signature"])
    assert claims["mandate_type"] == "intent"
    assert claims["mandate_id"] == draft["id"]


def test_confirm_twice_rejected(client):
    draft = client.post("/api/intent", json={"raw_text": FAKE_EXTRACTION.raw_text}).json()
    client.post(f"/api/intent/{draft['id']}/confirm")

    response = client.post(f"/api/intent/{draft['id']}/confirm")

    assert response.status_code == 400
    assert "cannot confirm" in response.json()["detail"]


def test_confirm_nonexistent_mandate_returns_404(client):
    response = client.post(f"/api/intent/{uuid.uuid4()}/confirm")
    assert response.status_code == 404


def test_get_nonexistent_mandate_returns_404(client):
    response = client.get(f"/api/intent/{uuid.uuid4()}")
    assert response.status_code == 404
