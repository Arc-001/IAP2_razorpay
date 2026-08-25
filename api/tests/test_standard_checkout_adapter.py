import razorpay

from app.adapters.standard_checkout import StandardCheckoutAdapter
from app.config import settings


class FakeOrderResource:
    def __init__(self, order_id="order_fake123", amount=50000, currency="INR"):
        self._order_id = order_id
        self._amount = amount
        self._currency = currency
        self.last_call_data = None

    def create(self, data):
        self.last_call_data = data
        return {"id": self._order_id, "amount": self._amount, "currency": self._currency}


class FakeUtility:
    def __init__(self, should_raise=False):
        self.should_raise = should_raise
        self.last_payload = None

    def verify_payment_signature(self, payload):
        self.last_payload = payload
        if self.should_raise:
            raise razorpay.errors.SignatureVerificationError("bad signature")


class FakeRazorpayClient:
    def __init__(self, should_raise=False):
        self.order = FakeOrderResource()
        self.utility = FakeUtility(should_raise=should_raise)


def test_create_charge_builds_order_and_client_payload(monkeypatch):
    monkeypatch.setattr(settings, "razorpay_key_id", "rzp_test_fake")
    fake_client = FakeRazorpayClient()
    adapter = StandardCheckoutAdapter(client=fake_client)

    result = adapter.create_charge(amount=50000, currency="INR", notes={"mandate_id": "abc"})

    assert fake_client.order.last_call_data == {
        "amount": 50000,
        "currency": "INR",
        "notes": {"mandate_id": "abc"},
    }
    assert result.reference == "order_fake123"
    assert result.adapter == "standard_checkout"
    assert result.client_payload["order_id"] == "order_fake123"
    assert result.client_payload["key_id"] == "rzp_test_fake"
    assert result.client_payload["amount"] == 50000


def test_verify_returns_true_on_valid_signature():
    adapter = StandardCheckoutAdapter(client=FakeRazorpayClient(should_raise=False))

    ok = adapter.verify(
        {"razorpay_order_id": "o", "razorpay_payment_id": "p", "razorpay_signature": "s"}
    )

    assert ok is True


def test_verify_returns_false_on_invalid_signature():
    adapter = StandardCheckoutAdapter(client=FakeRazorpayClient(should_raise=True))

    ok = adapter.verify(
        {"razorpay_order_id": "o", "razorpay_payment_id": "p", "razorpay_signature": "s"}
    )

    assert ok is False
