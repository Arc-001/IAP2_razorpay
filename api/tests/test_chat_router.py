import uuid
from types import SimpleNamespace

from app.orchestrator import orchestrator as orchestrator_module


def _response(content=None, tool_calls=None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls or [])
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeOpenAIClient:
    def __init__(self, responses):
        self._responses = iter(responses)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=lambda **kw: next(self._responses)))


def test_chat_endpoint_returns_state_and_reply(monkeypatch, client, customer_headers):
    fake = FakeOpenAIClient([_response(content="Tell me more.")])
    monkeypatch.setattr(orchestrator_module, "_client", lambda: fake)

    response = client.post("/api/chat", json={"message": "I want earbuds"}, headers=customer_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "DRAFTING_INTENT"
    assert body["reply"] == "Tell me more."
    assert body["intent_id"] is None


def test_chat_endpoint_404_on_unknown_intent_id(client, customer_headers):
    response = client.post(
        "/api/chat", json={"message": "hi", "intent_id": str(uuid.uuid4())}, headers=customer_headers
    )
    assert response.status_code == 404


def test_chat_endpoint_requires_authentication(client):
    response = client.post("/api/chat", json={"message": "hi"})
    assert response.status_code == 401


def test_chat_endpoint_rejects_a_merchant_token(client):
    register = client.post(
        "/api/auth/register",
        json={
            "email": "shop@example.com",
            "password": "hunter2",
            "role": "merchant",
            "name": "Owner",
            "merchant_name": "Shop",
        },
    )
    token = register.json()["access_token"]

    response = client.post("/api/chat", json={"message": "hi"}, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


def test_chat_endpoint_derives_customer_id_from_token_not_request_body(monkeypatch, client, customer_headers):
    """Before this change, a client could supply any customer_id directly in
    the request body and the server trusted it unverified — confirm that's
    no longer possible even if a client tries."""
    fake = FakeOpenAIClient([_response(content="ok")])
    monkeypatch.setattr(orchestrator_module, "_client", lambda: fake)

    other_customer_id = str(uuid.uuid4())
    response = client.post(
        "/api/chat",
        json={"message": "hi", "customer_id": other_customer_id},
        headers=customer_headers,
    )

    assert response.status_code == 200
    assert response.json()["customer_id"] != other_customer_id
