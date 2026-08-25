"""
THROWAWAY — live webhook verification for SCRUM-21.

Serves a Checkout page for the real order created via our own /api/payment
endpoint. Completing this payment triggers a real Razorpay webhook, routed
through the cloudflared tunnel back to our webhook receiver, which should
flip the corresponding payment_mandates row to executed/failed.

Run:
    uv run python scripts/webhook_test_checkout.py
Then open http://localhost:8899/
"""

import json

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

with open("/tmp/webhook_test_payment.json") as f:
    payment = json.load(f)

app = FastAPI()

PAGE = f"""
<!doctype html><html><body>
<h3>Webhook test — payment_mandate {payment['id']}</h3>
<p>order: {payment['client_payload']['order_id']} | amount: ₹{payment['amount'] / 100}</p>
<button id="pay">Pay</button>
<pre id="result"></pre>
<script src="https://checkout.razorpay.com/v1/checkout.js"></script>
<script>
document.getElementById('pay').onclick = function() {{
  var rzp = new Razorpay({{
    key: "{payment['client_payload']['key_id']}",
    amount: "{payment['client_payload']['amount']}",
    currency: "{payment['client_payload']['currency']}",
    order_id: "{payment['client_payload']['order_id']}",
    handler: function (response) {{
      document.getElementById('result').textContent =
        "Paid. payment_id=" + response.razorpay_payment_id +
        "\\nWaiting for webhook to update payment_mandates server-side...";
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8899)
