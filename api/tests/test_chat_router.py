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


def test_chat_endpoint_returns_state_and_reply(monkeypatch, client):
    fake = FakeOpenAIClient([_response(content="Tell me more.")])
    monkeypatch.setattr(orchestrator_module, "_client", lambda: fake)

    response = client.post("/api/chat", json={"message": "I want earbuds"})

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "DRAFTING_INTENT"
    assert body["reply"] == "Tell me more."
    assert body["intent_id"] is None


def test_chat_endpoint_404_on_unknown_intent_id(client):
    response = client.post("/api/chat", json={"message": "hi", "intent_id": str(uuid.uuid4())})
    assert response.status_code == 404
