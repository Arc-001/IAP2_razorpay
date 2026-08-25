"""
THROWAWAY SPIKE — SCRUM-13 / CLAUDE.md §11 Phase 0.

Not part of the app. Exercises order.create() -> Checkout widget -> HMAC
signature verification end to end, before any agent/mandate code exists.

The Checkout widget requires a live browser session (CLAUDE.md §6.5) — this
script creates the order headlessly, then serves a page for a human to
complete the payment in test mode. Verification happens automatically when
the browser posts the result back.

Run:
    uv run python scripts/spike_checkout_flow.py

Then open http://localhost:8899/ and pay with a UPI test handle:
    success@razorpay -> should verify as PASS
    failure@razorpay -> Checkout itself reports failure (no signature to verify)
"""

import razorpay
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.config import settings

if not settings.razorpay_key_id or not settings.razorpay_key_secret:
    raise SystemExit("Set RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET in api/.env first.")

client = razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))

order = client.order.create(data={
    "amount": 50000,  # paise -> ₹500.00
    "currency": "INR",
    "receipt": "spike-scrum-13",
})
print(f"\nOrder created: {order['id']}  (amount={order['amount']} {order['currency']})")
print("Open http://localhost:8899/ and complete payment with success@razorpay\n")

app = FastAPI()

PAGE = f"""
<!doctype html><html><body>
<h3>SCRUM-13 spike — order {order['id']}</h3>
<button id="pay">Pay ₹500</button>
<pre id="result"></pre>
<script src="https://checkout.razorpay.com/v1/checkout.js"></script>
<script>
document.getElementById('pay').onclick = function() {{
  var rzp = new Razorpay({{
    key: "{settings.razorpay_key_id}",
    amount: "{order['amount']}",
    currency: "{order['currency']}",
    order_id: "{order['id']}",
    handler: function (response) {{
      fetch('/verify', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify(response)
      }}).then(r => r.json()).then(data => {{
        document.getElementById('result').textContent = JSON.stringify(data, null, 2);
      }});
    }}
  }});
  rzp.open();
}};
</script>
</body></html>
"""


@app.get("/", response_class=HTMLResponse)
def index():
    return PAGE


@app.post("/verify")
async def verify(request: Request):
    body = await request.json()
    try:
        # Use our own server-recorded order_id (CLAUDE.md §6.8), never the
        # one the client echoes back, even though in this spike they're
        # the same order created above.
        client.utility.verify_payment_signature({
            "razorpay_order_id": order["id"],
            "razorpay_payment_id": body["razorpay_payment_id"],
            "razorpay_signature": body["razorpay_signature"],
        })
        verified = True
    except razorpay.errors.SignatureVerificationError:
        verified = False

    print(f"Signature verification: {'PASS' if verified else 'FAIL'} — {body}")
    return JSONResponse({"verified": verified, **body})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8899)
