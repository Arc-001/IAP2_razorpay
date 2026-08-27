import json
from types import SimpleNamespace

from app.orchestrator import orchestrator as orchestrator_module


def _tool_call(call_id, name, arguments):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=json.dumps(arguments)))


def _message(content=None, tool_calls=None):
    return SimpleNamespace(content=content, tool_calls=tool_calls or [])


def _response(message):
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


def _propose_earbuds_intent(client, headers):
    call = _tool_call(
        "call_1",
        "propose_intent",
        {"product_query": "earbuds", "quantity": 1, "budget_paise": None, "constraints": []},
    )
    fake = FakeOpenAIClient(
        [_response(_message(tool_calls=[call])), _response(_message(content="Confirm?"))]
    )
    return fake


def test_orders_empty_for_a_fresh_account(client):
    headers = _register(client, "orders1@example.com")

    response = client.get("/api/me/orders", headers=headers)

    assert response.status_code == 200
    assert response.json() == []


def test_orders_shows_a_drafted_intent(monkeypatch, client):
    headers = _register(client, "orders2@example.com")
    fake = _propose_earbuds_intent(client, headers)
    monkeypatch.setattr(orchestrator_module, "_client", lambda: fake)

    client.post("/api/chat", json={"message": "I want earbuds"}, headers=headers)

    response = client.get("/api/me/orders", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["product_query"] == "earbuds"
    assert body[0]["intent_status"] == "draft"
    assert body[0]["cart_id"] is None
    assert body[0]["payment_id"] is None


def test_orders_requires_authentication(client):
    response = client.get("/api/me/orders")
    assert response.status_code == 401


def test_cannot_see_another_customers_orders(monkeypatch, client):
    headers_a = _register(client, "orders-a@example.com")
    headers_b = _register(client, "orders-b@example.com")
    fake = _propose_earbuds_intent(client, headers_a)
    monkeypatch.setattr(orchestrator_module, "_client", lambda: fake)

    client.post("/api/chat", json={"message": "I want earbuds"}, headers=headers_a)

    response = client.get("/api/me/orders", headers=headers_b)
    assert response.json() == []
