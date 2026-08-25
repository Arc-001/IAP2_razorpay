import json
from types import SimpleNamespace

from app.services import intent_extraction


def _fake_openai_response(arguments: dict):
    tool_call = SimpleNamespace(function=SimpleNamespace(arguments=json.dumps(arguments)))
    message = SimpleNamespace(tool_calls=[tool_call])
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


def test_extract_intent_parses_tool_call(monkeypatch):
    expected_args = {
        "product_query": "wireless earbuds",
        "quantity": 1,
        "budget_paise": 300000,
        "constraints": [],
    }

    class FakeClient:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    assert kwargs["tool_choice"]["function"]["name"] == "propose_intent"
                    return _fake_openai_response(expected_args)

    monkeypatch.setattr(intent_extraction, "_client", lambda: FakeClient())

    result = intent_extraction.extract_intent("I want wireless earbuds under 3000 rupees")

    assert result.product_query == "wireless earbuds"
    assert result.budget_paise == 300000
    assert result.raw_text == "I want wireless earbuds under 3000 rupees"


def test_extract_intent_defaults_missing_optional_fields(monkeypatch):
    class FakeClient:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    return _fake_openai_response({"product_query": "power bank", "quantity": 2})

    monkeypatch.setattr(intent_extraction, "_client", lambda: FakeClient())

    result = intent_extraction.extract_intent("get me 2 power banks")

    assert result.quantity == 2
    assert result.budget_paise is None
    assert result.constraints == []
