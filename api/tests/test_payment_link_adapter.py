import razorpay

from app.adapters.payment_link import PaymentLinkAdapter


class FakePaymentLinkResource:
    def __init__(self, link_id="plink_fake123", short_url="https://rzp.io/i/fake123"):
        self._link_id = link_id
        self._short_url = short_url
        self.last_call_data = None

    def create(self, data):
        self.last_call_data = data
        return {"id": self._link_id, "short_url": self._short_url}


class FakeUtility:
    def __init__(self, should_raise=False):
        self.should_raise = should_raise
        self.last_payload = None

    def verify_payment_link_signature(self, payload):
        self.last_payload = payload
        if self.should_raise:
            raise razorpay.errors.SignatureVerificationError("bad signature")


class FakeRazorpayClient:
    def __init__(self, should_raise=False):
        self.payment_link = FakePaymentLinkResource()
        self.utility = FakeUtility(should_raise=should_raise)


def test_create_charge_builds_payment_link_and_client_payload():
    fake_client = FakeRazorpayClient()
    adapter = PaymentLinkAdapter(client=fake_client)

    result = adapter.create_charge(amount=254800, currency="INR", notes={"mandate_id": "abc"})

    assert fake_client.payment_link.last_call_data == {
        "amount": 254800,
        "currency": "INR",
        "notes": {"mandate_id": "abc"},
        "reminder_enable": True,
    }
    assert result.reference == "plink_fake123"
    assert result.adapter == "payment_link"
    assert result.client_payload["short_url"] == "https://rzp.io/i/fake123"
    assert result.client_payload["payment_link_id"] == "plink_fake123"


def test_verify_returns_true_on_valid_signature():
    adapter = PaymentLinkAdapter(client=FakeRazorpayClient(should_raise=False))

    ok = adapter.verify(
        {
            "payment_link_id": "plink_x",
            "payment_link_reference_id": "ref_x",
            "payment_link_status": "paid",
            "razorpay_payment_id": "pay_x",
            "razorpay_signature": "s",
        }
    )

    assert ok is True


def test_verify_returns_false_on_invalid_signature():
    adapter = PaymentLinkAdapter(client=FakeRazorpayClient(should_raise=True))

    ok = adapter.verify(
        {
            "payment_link_id": "plink_x",
            "payment_link_reference_id": "ref_x",
            "payment_link_status": "paid",
            "razorpay_payment_id": "pay_x",
            "razorpay_signature": "s",
        }
    )

    assert ok is False
