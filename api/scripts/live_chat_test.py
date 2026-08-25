"""THROWAWAY — live end-to-end orchestrator test against the real API server
and real OpenRouter model, driving the full state machine turn by turn."""

import httpx

BASE = "http://localhost:8123"


def turn(message, ctx, history):
    payload = {"message": message, "history": history, **ctx}
    resp = httpx.post(f"{BASE}/api/chat", json=payload, timeout=60)
    resp.raise_for_status()
    body = resp.json()
    print(f"\n>>> {message}")
    print(f"state={body['state']}")
    print(f"reply={body['reply']}")
    for tc in body["tool_calls"]:
        print(f"  tool={tc['tool']} args={tc['args']}")

    history.extend(body["new_messages"])

    for key in ("intent_id", "cart_id", "payment_id"):
        if body[key]:
            ctx[key] = body[key]
    return body


ctx = {}
history = []

turn("I want wireless earbuds, budget under 3000 rupees", ctx, history)
turn("yes, confirm it", ctx, history)
turn("what earbuds do you have?", ctx, history)
turn("add the Wireless Earbuds Pro, one unit. Ship to 42 MG Road, Bangalore", ctx, history)
turn("yes confirm the cart", ctx, history)
turn("go ahead and set up payment", ctx, history)

print("\nfinal ctx:", ctx)
