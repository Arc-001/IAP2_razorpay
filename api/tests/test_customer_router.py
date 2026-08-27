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


def _register(client, email):
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "hunter2", "role": "customer", "name": "Someone"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_chatting_creates_a_conversation_visible_in_my_conversations(monkeypatch, client):
    headers = _register(client, "history1@example.com")
    fake = FakeOpenAIClient([_response(content="Tell me more.")])
    monkeypatch.setattr(orchestrator_module, "_client", lambda: fake)

    chat_response = client.post("/api/chat", json={"message": "I want earbuds"}, headers=headers)
    conversation_id = chat_response.json()["conversation_id"]

    listing = client.get("/api/me/conversations", headers=headers)
    assert listing.status_code == 200
    ids = [c["id"] for c in listing.json()]
    assert conversation_id in ids
    assert listing.json()[0]["title"] == "I want earbuds"


def test_second_turn_reuses_the_same_conversation_and_accumulates_history(monkeypatch, client):
    headers = _register(client, "history2@example.com")
    fake = FakeOpenAIClient([_response(content="first reply"), _response(content="second reply")])
    monkeypatch.setattr(orchestrator_module, "_client", lambda: fake)

    first = client.post("/api/chat", json={"message": "hello"}, headers=headers)
    conversation_id = first.json()["conversation_id"]

    second = client.post(
        "/api/chat", json={"message": "more info", "conversation_id": conversation_id}, headers=headers
    )
    assert second.json()["conversation_id"] == conversation_id

    detail = client.get(f"/api/me/conversations/{conversation_id}", headers=headers)
    assert detail.status_code == 200
    body = detail.json()
    assert len(body["display_log"]) == 4
    assert body["display_log"][0]["text"] == "hello"
    assert body["display_log"][2]["text"] == "more info"


def test_cannot_fetch_another_customers_conversation(monkeypatch, client):
    headers_a = _register(client, "alice-hist@example.com")
    headers_b = _register(client, "bob-hist@example.com")
    fake = FakeOpenAIClient([_response(content="hi")])
    monkeypatch.setattr(orchestrator_module, "_client", lambda: fake)

    chat_response = client.post("/api/chat", json={"message": "hello"}, headers=headers_a)
    conversation_id = chat_response.json()["conversation_id"]

    response = client.get(f"/api/me/conversations/{conversation_id}", headers=headers_b)
    assert response.status_code == 404


def test_get_unknown_conversation_id_returns_404(client):
    headers = _register(client, "history3@example.com")
    response = client.get(f"/api/me/conversations/{uuid.uuid4()}", headers=headers)
    assert response.status_code == 404


def test_my_conversations_requires_authentication(client):
    response = client.get("/api/me/conversations")
    assert response.status_code == 401


def test_my_conversations_rejects_a_merchant_token(client):
    register = client.post(
        "/api/auth/register",
        json={
            "email": "shop-hist@example.com",
            "password": "hunter2",
            "role": "merchant",
            "name": "Owner",
            "merchant_name": "Shop",
        },
    )
    token = register.json()["access_token"]

    response = client.get("/api/me/conversations", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403
