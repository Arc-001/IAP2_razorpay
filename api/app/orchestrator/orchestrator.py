import json
from dataclasses import dataclass

from openai import OpenAI
from sqlalchemy.orm import Session

from app.config import settings
from app.orchestrator.context import MandateContext
from app.orchestrator.state import AgentState, derive_state
from app.orchestrator.tools import get_tool, get_tools_for_state

SYSTEM_PROMPT = (
    "You are a shopping assistant executing a strictly gated purchase flow: "
    "Intent -> Cart -> Payment -> Outcome. You can only call the tools "
    "currently made available to you — they change as the transaction "
    "progresses through states. Never invent a tool that isn't offered. "
    "\n\n"
    "At every turn, end your reply by telling the customer plainly what they "
    "can do next (e.g. 'confirm this, or tell me what to change' / 'pick one "
    "of these, or ask to see more' / 'confirm the cart, or add another item "
    "first') — never leave them guessing what a valid next message looks like. "
    "\n\n"
    "A draft intent or cart is never locked — propose_intent and propose_cart "
    "both stay available right up until the customer actually confirms, so if "
    "they add detail or want another item before confirming, just redraft "
    "with propose_intent/propose_cart again (it's cheap and safe: nothing is "
    "signed until confirm_intent/confirm_cart). Never tell the customer a "
    "draft can't be changed. "
    "Only treat a clear, unambiguous yes as confirmation before calling "
    "confirm_intent or confirm_cart — a vague, confused, or non-committal reply "
    "('hmm?', 'what?', silence-equivalent) is not consent; ask them to confirm "
    "plainly instead of guessing. "
    "\n\n"
    "You can call more than one tool in a row within the same reply when it "
    "genuinely moves the customer forward — e.g. the instant confirm_intent "
    "succeeds, go ahead and call search_catalog too and show results in that "
    "same reply, rather than stopping at 'confirmed' and waiting to be asked. "
    "Likewise, once an upsell is accepted or declined, go straight into "
    "propose_cart in that same reply instead of pausing first. Never chain "
    "into confirm_intent, confirm_cart, or create_payment on your own "
    "initiative, though — those only ever fire in direct response to the "
    "customer's own explicit words in this turn. "
    "\n\n"
    "When calling search_catalog, build the query from the product itself (e.g. "
    "'usb-c charger'), never from the customer's literal sentence verbatim. "
    "search_catalog spans every merchant — when the same or a similar product "
    "shows up from more than one, tell the customer and recommend the cheapest "
    "option unless they've said they prefer a specific merchant. "
    "\n\n"
    "Once the customer's main items are settled, consider suggest_upsell before "
    "confirming the cart — at most one relevant add-on, offered once, with zero "
    "pressure if declined. Never bring it up again once the cart is confirmed. "
    "\n\n"
    "Whenever the customer asks about payment status, or claims a payment "
    "succeeded or failed, ALWAYS call check_payment_status first and report "
    "exactly what it returns — check_payment_status is available throughout "
    "payment, never claim otherwise. Never agree with the customer's own "
    "unverified claim instead of checking; if the tool says 'pending', say "
    "plainly that it's still pending, even if they insist otherwise. Only call "
    "retry_payment or cancel_payment when the tool's own status is 'failed', "
    "and never invent instructions like 'use your payment interface' — the "
    "tools are the only way anything actually happens. If a payment fails, say "
    "so plainly and directly — never stay silent — and offer a clear choice "
    "between retrying or cancelling."
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


UNAVAILABLE_REPLY = "I'm having trouble reaching the assistant right now — please try that again in a moment."


def _client() -> OpenAI:
    return OpenAI(base_url=settings.openrouter_base_url, api_key=settings.openrouter_api_key)


def _safe_complete(client: OpenAI, **kwargs):
    """Some OpenRouter provider routes occasionally return a response with
    `choices=None` (observed live, not just in theory) rather than raising —
    a bare `response.choices[0]` then crashes the whole request with an
    unhandled 500, even though nothing has been persisted yet at that point.
    Retry once (transient, not a real error condition); if it still comes
    back empty, let the caller fall back gracefully instead of blowing up."""
    for _ in range(2):
        response = client.chat.completions.create(**kwargs)
        if response.choices:
            return response
    return None


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


# Multiple tool-calling rounds are allowed within a single turn (e.g.
# confirm_intent immediately followed by search_catalog, or decline_upsell
# immediately followed by propose_cart) — state is re-derived after every
# round, so the tools on offer always reflect what's actually legal *now*.
# This is safe, not a loophole: nothing that requires human sign-off can
# repeat within a turn, because the tool that performs it (confirm_intent,
# confirm_cart, ...) simply disappears from the newly-derived state once
# it's been called — the model can't re-trigger it, only move forward.
# MAX_ROUNDS is a pure safety valve against a model that keeps calling
# tools without ever settling on a reply; it should never normally bind.
MAX_ROUNDS = 5


def run_turn(
    db: Session,
    context: MandateContext,
    user_message: str,
    history: list[dict] | None = None,
) -> OrchestratorTurnResult:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + (history or [])
    messages.append({"role": "user", "content": user_message})
    new_messages = [{"role": "user", "content": user_message}]

    client = _client()
    current_context = context
    tool_call_log: list[dict] = []
    state = derive_state(db, current_context.intent_id, current_context.cart_id, current_context.payment_id)

    for round_num in range(MAX_ROUNDS):
        tools = get_tools_for_state(state)
        response = _safe_complete(
            client,
            model=settings.openrouter_model,
            messages=messages,
            tools=[t.schema for t in tools] if tools else None,
        )
        if response is None:
            # If tools already ran this turn (e.g. confirm_intent succeeded
            # before this round's completion came back empty), say what
            # actually happened instead of a generic "can't reach it" — the
            # mandate really was signed, telling the customer otherwise
            # would be actively misleading.
            reply = _fallback_reply(tool_call_log) if tool_call_log else UNAVAILABLE_REPLY
            new_messages.append({"role": "assistant", "content": reply})
            new_state = derive_state(
                db, current_context.intent_id, current_context.cart_id, current_context.payment_id
            )
            return OrchestratorTurnResult(
                state=new_state,
                context=current_context,
                reply=reply,
                tool_calls=tool_call_log,
                new_messages=new_messages,
            )
        message = response.choices[0].message

        if not message.tool_calls:
            reply = message.content or (_fallback_reply(tool_call_log) if tool_call_log else "")
            new_messages.append({"role": "assistant", "content": reply})
            break

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

        # Tools may have advanced the state (e.g. confirm_intent just ran) —
        # re-derive before the next round so the model sees what's legal now.
        state = derive_state(db, current_context.intent_id, current_context.cart_id, current_context.payment_id)

        if round_num == MAX_ROUNDS - 1:
            # Safety valve tripped — force a plain-language summary. Omitting
            # `tools` here means no further call is structurally possible.
            final = _safe_complete(client, model=settings.openrouter_model, messages=messages)
            reply = (final.choices[0].message.content if final else None) or _fallback_reply(tool_call_log)
            new_messages.append({"role": "assistant", "content": reply})

    new_state = derive_state(db, current_context.intent_id, current_context.cart_id, current_context.payment_id)
    return OrchestratorTurnResult(
        state=new_state, context=current_context, reply=reply, tool_calls=tool_call_log, new_messages=new_messages
    )
