import json
from types import SimpleNamespace

from app.services import tag_generation


def _fake_openai_response(arguments: dict):
    tool_call = SimpleNamespace(function=SimpleNamespace(arguments=json.dumps(arguments)))
    message = SimpleNamespace(tool_calls=[tool_call])
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_generate_tags_parses_tool_call(monkeypatch):
    class FakeClient:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    assert kwargs["tool_choice"]["function"]["name"] == "suggest_tags"
                    return _fake_openai_response({"tags": ["wireless", "earbuds", "bluetooth"]})

    monkeypatch.setattr(tag_generation, "_client", lambda: FakeClient())

    tags = tag_generation.generate_tags_for_product("Wireless Earbuds Pro", "ANC true wireless earbuds", "audio")

    assert tags == ["wireless", "earbuds", "bluetooth"]


def test_generate_tags_returns_empty_list_on_client_error(monkeypatch):
    class FailingClient:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    raise RuntimeError("OpenRouter is down")

    monkeypatch.setattr(tag_generation, "_client", lambda: FailingClient())

    tags = tag_generation.generate_tags_for_product("Phone Case", "A case", "accessories")

    assert tags == []


def test_generate_tags_returns_empty_list_on_malformed_response(monkeypatch):
    class FakeClient:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=[]))])

    monkeypatch.setattr(tag_generation, "_client", lambda: FakeClient())

    tags = tag_generation.generate_tags_for_product("Phone Case", "A case", "accessories")

    assert tags == []
