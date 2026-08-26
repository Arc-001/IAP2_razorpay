"""THROWAWAY — live end-to-end verification for SCRUM-24 (failure branch).

Drives the real orchestrator + real OpenRouter model + real Postgres through:
  confirmed cart -> payment -> simulated payment.failed webhook ->
  agent explains failure -> retry_payment -> simulated failure again ->
  cancel_payment -> TERMINAL.

The webhook is simulated (HMAC-signed with the real webhook secret, same as
Razorpay would do) rather than driven through a live Checkout browser click,
since this script only needs to exercise our own failure-branch code, not
Razorpay's payment processing itself.

Run:
    uv run python scripts/live_failure_branch_test.py
"""

import hashlib
import hmac
import json

import httpx

from app.config import settings

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
        print(f"  tool={tc['tool']} args={tc['args']} output={tc['output']}")

    history.extend(body["new_messages"])
    for key in ("intent_id", "cart_id", "payment_id"):
        if body[key]:
            ctx[key] = body[key]
    return body


def fail_payment_via_webhook(payment_id: str):
    body = json.dumps(
        {
            "event": "payment.failed",
            "payload": {
                "payment": {
                    "entity": {"id": f"pay_sim_{payment_id[:8]}", "amount": 1, "notes": {"mandate_id": payment_id}}
                }
            },
        }
    ).encode()
    signature = hmac.new(settings.razorpay_webhook_secret.encode(), body, hashlib.sha256).hexdigest()
    resp = httpx.post(
        f"{BASE}/api/webhooks/razorpay",
        content=body,
        headers={"X-Razorpay-Signature": signature, "Content-Type": "application/json"},
    )
    resp.raise_for_status()
    print(f"\n[simulated payment.failed webhook for {payment_id}] -> {resp.json()}")


ctx = {}
history = []

turn("I want wireless earbuds, budget under 3000 rupees", ctx, history)
turn("yes, confirm it", ctx, history)
turn("what earbuds do you have?", ctx, history)
turn("add the Wireless Earbuds Pro, one unit. Ship to 42 MG Road, Bangalore", ctx, history)
turn("yes confirm the cart", ctx, history)
body = turn("go ahead and set up payment", ctx, history)

first_payment_id = ctx["payment_id"]
fail_payment_via_webhook(first_payment_id)

body = turn("has my payment gone through?", ctx, history)
assert body["state"] == "PAYMENT_FAILED", f"expected PAYMENT_FAILED, got {body['state']}"

body = turn("let's try again", ctx, history)
assert body["state"] == "EXECUTING_PAYMENT", f"expected EXECUTING_PAYMENT, got {body['state']}"
retried_payment_id = ctx["payment_id"]
assert retried_payment_id != first_payment_id, "retry must create a new payment mandate, not reuse the failed one"

fail_payment_via_webhook(retried_payment_id)
body = turn("that failed too", ctx, history)
assert body["state"] == "PAYMENT_FAILED"

body = turn("just cancel it", ctx, history)
assert body["state"] == "TERMINAL", f"expected TERMINAL, got {body['state']}"

print("\nALL ASSERTIONS PASSED")
print("final ctx:", ctx)
