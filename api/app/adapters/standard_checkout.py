import razorpay

from app.adapters.payment_provider import ChargeResult
from app.config import settings


class StandardCheckoutAdapter:
    """Website surface: Order + embedded Checkout widget (CLAUDE.md §6.3, §6.5).
    order_id is mandatory and ties the payment to the order server-side."""

    def __init__(self, client: razorpay.Client | None = None):
        self.client = client or razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))

    def create_charge(self, amount: int, currency: str, notes: dict) -> ChargeResult:
        order = self.client.order.create(data={"amount": amount, "currency": currency, "notes": notes})
        return ChargeResult(
            reference=order["id"],
            adapter="standard_checkout",
            client_payload={
                "key_id": settings.razorpay_key_id,
                "order_id": order["id"],
                "amount": order["amount"],
                "currency": order["currency"],
            },
        )

    def verify(self, payload: dict) -> bool:
        """payload keys: razorpay_order_id, razorpay_payment_id, razorpay_signature
        (CLAUDE.md §6.8). Caller must pass its own server-recorded order_id,
        never one echoed by the client."""
        try:
            self.client.utility.verify_payment_signature(payload)
            return True
        except razorpay.errors.SignatureVerificationError:
            return False
