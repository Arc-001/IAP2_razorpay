import razorpay

from app.adapters.payment_provider import ChargeResult
from app.config import settings


class PaymentLinkAdapter:
    """MCP/Claude Desktop surface (CLAUDE.md §6.2, §9): Claude has no browser
    to open a Checkout widget in, so this hands back a hosted, self-contained
    Payment Link URL instead — a plain string Claude can present as a link.

    Verification for this surface relies exclusively on the webhook (§6.7's
    own recommended pattern) since there's no browser to run a client-side
    callback/redirect through. verify() is implemented for interface parity
    with StandardCheckoutAdapter and the case a callback_url flow is added
    later, but nothing in this codebase calls it yet — same as the other
    adapter."""

    def __init__(self, client: razorpay.Client | None = None):
        self.client = client or razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))

    def create_charge(self, amount: int, currency: str, notes: dict) -> ChargeResult:
        link = self.client.payment_link.create(
            data={
                "amount": amount,
                "currency": currency,
                "notes": notes,
                "reminder_enable": True,
            }
        )
        return ChargeResult(
            reference=link["id"],
            adapter="payment_link",
            client_payload={"short_url": link["short_url"], "payment_link_id": link["id"]},
        )

    def verify(self, payload: dict) -> bool:
        """payload keys: payment_link_id, payment_link_reference_id,
        payment_link_status, razorpay_payment_id, razorpay_signature."""
        try:
            self.client.utility.verify_payment_link_signature(payload)
            return True
        except razorpay.errors.SignatureVerificationError:
            return False
