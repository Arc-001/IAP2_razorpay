"""AI-generated product tags (CLAUDE.md §13 / SCRUM-44) — mirrors
intent_extraction.py's forced-single-tool-call pattern exactly. This is a
one-off structured completion, not part of the interactive orchestrator."""

import json

from openai import OpenAI

from app.config import settings
from app.schemas.merchant import TagSuggestion

SYSTEM_PROMPT = (
    "You generate short browse/search tags for an e-commerce product listing. "
    "Call suggest_tags with 3-6 concise, lowercase, single-or-two-word tags based "
    "only on the given name/description/category — never invent features or "
    "attributes that weren't stated."
)

_TOOL = {
    "type": "function",
    "function": {
        "name": "suggest_tags",
        "description": "Suggest browse/search tags for a product listing.",
        "parameters": TagSuggestion.model_json_schema(),
    },
}


def _client() -> OpenAI:
    return OpenAI(base_url=settings.openrouter_base_url, api_key=settings.openrouter_api_key)


def generate_tags_for_product(name: str, description: str | None, category: str | None) -> list[str]:
    """Best-effort: a tagging failure (LLM outage, malformed response, ...)
    must never block product creation, so every failure mode here degrades
    to an empty tag list instead of propagating."""
    try:
        user_content = f"Name: {name}\nDescription: {description or '(none)'}\nCategory: {category or '(none)'}"
        response = _client().chat.completions.create(
            model=settings.openrouter_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            tools=[_TOOL],
            tool_choice={"type": "function", "function": {"name": "suggest_tags"}},
        )
        tool_call = response.choices[0].message.tool_calls[0]
        args = json.loads(tool_call.function.arguments)
        return TagSuggestion(**args).tags
    except Exception:  # noqa: BLE001 — any failure here degrades to no tags, by design
        return []
