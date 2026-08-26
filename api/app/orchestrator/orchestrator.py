import json
from dataclasses import dataclass

from openai import OpenAI
from sqlalchemy.orm import Session

from app.config import settings
from app.orchestrator.context import MandateContext
from app.orchestrator.state import AgentState, derive_state
from app.orchestrator.tools import get_tool, get_tools_for_state

SYSTEM_PROMPT = (
    "You are a shopping assistant executing a strictly gated purchase flow. "
    "You can only call the tools currently made available to you — they change "
    "as the transaction progresses through states. Never invent a tool that "
    "isn't offered. Confirm each step in plain language before moving on. "
    "If a payment fails, say so plainly and directly — never stay silent about "
    "it — and offer the customer a choice between retrying or cancelling."
)


@dataclass
class OrchestratorTurnResult:
    state: AgentState
    context: MandateContext
    reply: str
    tool_calls: list[dict]
    new_messages: list[dict]
    """Everything this turn added, starting with the user message. The
    caller (stateless per-turn design, CLAUDE.md §4) appends this to its
    stored history verbatim for the next turn — a lossy summary (e.g. just
    the reply text) drops tool-result details like exact product ids, which
    causes the model to lose track mid-flow."""


def _client() -> OpenAI:
    return OpenAI(base_url=settings.openrouter_base_url, api_key=settings.openrouter_api_key)


def _fallback_reply(tool_call_log: list[dict]) -> str:
    """Some OpenRouter backends occasionally return empty content on the
    post-tool-call summary completion. Never hand the caller an empty
    reply — synthesize one from the tool outcomes instead."""
    parts = []
    for tc in tool_call_log:
        if "error" in tc["output"]:
            parts.append(f"{tc['tool']} failed: {tc['output']['error']}")
        else:
            parts.append(f"{tc['tool']} completed.")
    return " ".join(parts) or "Okay."


def run_turn(
    db: Session,
    context: MandateContext,
    user_message: str,
    history: list[dict] | None = None,
) -> OrchestratorTurnResult:
    state = derive_state(db, context.intent_id, context.cart_id, context.payment_id)
    tools = get_tools_for_state(state)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + (history or [])
    messages.append({"role": "user", "content": user_message})
    new_messages = [{"role": "user", "content": user_message}]

    client = _client()
    response = client.chat.completions.create(
        model=settings.openrouter_model,
        messages=messages,
        tools=[t.schema for t in tools] if tools else None,
    )
    message = response.choices[0].message

    tool_call_log = []
    current_context = context

    if message.tool_calls:
        assistant_tool_message = {
            "role": "assistant",
            "content": message.content,
            "tool_calls": [
                {"id": c.id, "type": "function", "function": {"name": c.function.name, "arguments": c.function.arguments}}
                for c in message.tool_calls
            ],
        }
        messages.append(assistant_tool_message)
        new_messages.append(assistant_tool_message)

        for call in message.tool_calls:
            tool_def = get_tool(state, call.function.name)
            args = json.loads(call.function.arguments or "{}")

            if tool_def is None:
                # Defense in depth: the model tried a tool not valid for this
                # state — structurally shouldn't happen since we only sent
                # valid tools, but never trust the model over the gate.
                output = {"error": f"'{call.function.name}' is not available in the current state"}
            else:
                try:
                    result = tool_def.handler(db, current_context, args, user_message)
                    output = result.output
                    current_context = result.context
                except (LookupError, ValueError) as e:
                    output = {"error": str(e)}

            tool_call_log.append({"tool": call.function.name, "args": args, "output": output})
            tool_message = {"role": "tool", "tool_call_id": call.id, "content": json.dumps(output)}
            messages.append(tool_message)
            new_messages.append(tool_message)

        # One tool round per turn — omitting `tools` here means no further
        # tool call is structurally possible, forcing a plain-language
        # summary rather than letting the model chain calls unbounded.
        # (tool_choice="none" without a tools list is unreliable across
        # OpenRouter backends and produced empty replies in testing.)
        final = client.chat.completions.create(
            model=settings.openrouter_model,
            messages=messages,
        )
        reply = final.choices[0].message.content or _fallback_reply(tool_call_log)
    else:
        reply = message.content or ""

    new_messages.append({"role": "assistant", "content": reply})

    new_state = derive_state(db, current_context.intent_id, current_context.cart_id, current_context.payment_id)
    return OrchestratorTurnResult(
        state=new_state, context=current_context, reply=reply, tool_calls=tool_call_log, new_messages=new_messages
    )
