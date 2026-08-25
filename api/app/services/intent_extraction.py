import json

from openai import OpenAI

from app.config import settings
from app.schemas.intent import IntentExtraction, IntentExtractionResponse

SYSTEM_PROMPT = (
    "You extract a structured purchase intent from a customer's natural-language request. "
    "Call propose_intent with your best extraction. Do not invent constraints the customer "
    "did not state. If budget isn't mentioned, leave budget_paise null."
)

_TOOL = {
    "type": "function",
    "function": {
        "name": "propose_intent",
        "description": "Propose a structured purchase intent extracted from the customer's request.",
        "parameters": IntentExtraction.model_json_schema(),
    },
}


def _client() -> OpenAI:
    return OpenAI(base_url=settings.openrouter_base_url, api_key=settings.openrouter_api_key)


def extract_intent(raw_text: str) -> IntentExtractionResponse:
    response = _client().chat.completions.create(
        model=settings.openrouter_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": raw_text},
        ],
        tools=[_TOOL],
        tool_choice={"type": "function", "function": {"name": "propose_intent"}},
    )

    tool_call = response.choices[0].message.tool_calls[0]
    args = json.loads(tool_call.function.arguments)
    return IntentExtractionResponse(raw_text=raw_text, **args)
