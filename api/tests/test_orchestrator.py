import json
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from app.adapters.payment_provider import ChargeResult
from app.models import (
    CartMandate,
    Customer,
    IntentMandate,
    Merchant,
    PaymentMandate,
    PriceHistory,
    Product,
)
from app.orchestrator import orchestrator as orchestrator_module
from app.orchestrator.context import MandateContext
from app.orchestrator.orchestrator import run_turn
from app.orchestrator.state import AgentState
from app.services.price_history import record_price_change


def _tool_call(call_id, name, arguments):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=json.dumps(arguments)))


def _message(content=None, tool_calls=None):
    return SimpleNamespace(content=content, tool_calls=tool_calls or [])


def _response(message):
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _empty_response():
    """Simulates the malformed OpenRouter response observed live in testing:
    choices=None rather than a raised exception or an empty list."""
    return SimpleNamespace(choices=None)


class FakeOpenAIClient:
    def __init__(self, responses):
        self._responses = iter(responses)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return next(self._responses)


def _patch_client(monkeypatch, responses):
    fake = FakeOpenAIClient(responses)
    monkeypatch.setattr(orchestrator_module, "_client", lambda: fake)
    return fake


def _customer(db_session, saved_address=None) -> Customer:
    customer = Customer(name="Test", saved_address=saved_address)
    db_session.add(customer)
    db_session.flush()
    return customer


def _confirmed_intent(db_session, customer, budget_paise=None) -> IntentMandate:
    intent = IntentMandate(
        customer_id=customer.id,
        raw_text="x",
        structured_json={"budget_paise": budget_paise},
        status="confirmed",
        signature="s",
        confirmed_at=datetime.now(UTC),
    )
    db_session.add(intent)
    db_session.flush()
    return intent


def test_drafting_intent_only_exposes_propose_intent(monkeypatch, db_session):
    fake = _patch_client(
        monkeypatch, [_response(_message(content="Tell me more about what you're looking for."))]
    )

    result = run_turn(db_session, MandateContext(), "I want some earbuds")

    tool_names = {t["function"]["name"] for t in fake.calls[0]["tools"]}
    assert tool_names == {"propose_intent"}
    assert result.state == AgentState.DRAFTING_INTENT
    assert result.reply == "Tell me more about what you're looking for."


def test_propose_intent_tool_call_advances_state_and_persists(monkeypatch, db_session):
    call = _tool_call(
        "call_1",
        "propose_intent",
        {"product_query": "wireless earbuds", "quantity": 1, "budget_paise": 300000, "constraints": []},
    )
    _patch_client(
        monkeypatch,
        [
            _response(_message(tool_calls=[call])),
            _response(_message(content="I've drafted your intent. Confirm?")),
        ],
    )

    result = run_turn(db_session, MandateContext(), "I want wireless earbuds under 3000 rupees")

    assert result.state == AgentState.AWAITING_INTENT_OK
    assert result.context.intent_id is not None
    assert result.tool_calls[0]["tool"] == "propose_intent"
    assert result.tool_calls[0]["output"]["status"] == "draft"


def test_redrafting_intent_before_confirm_supersedes_the_old_draft(monkeypatch, db_session):
    customer = _customer(db_session)
    intent = IntentMandate(
        customer_id=customer.id,
        raw_text="charger",
        structured_json={"product_query": "charger", "quantity": 1, "budget_paise": None, "constraints": []},
        status="draft",
    )
    db_session.add(intent)
    db_session.commit()

    call = _tool_call(
        "call_1",
        "propose_intent",
        {"product_query": "usb-c fast charger", "quantity": 1, "budget_paise": None, "constraints": ["type-c", "fast"]},
    )
    _patch_client(
        monkeypatch,
        [_response(_message(tool_calls=[call])), _response(_message(content="Updated. Confirm?"))],
    )

    result = run_turn(
        db_session,
        MandateContext(customer_id=customer.id, intent_id=intent.id),
        "actually, make it type-c and fast",
    )

    assert result.state == AgentState.AWAITING_INTENT_OK
    assert result.context.intent_id != intent.id
    assert result.tool_calls[0]["output"]["structured"]["constraints"] == ["type-c", "fast"]


def test_awaiting_intent_ok_exposes_propose_and_confirm_intent(monkeypatch, db_session):
    """propose_intent stays available so the customer can redraft with new
    detail before confirming (e.g. "actually make it fast-charging") — safe
    since nothing is signed until confirm_intent."""
    customer = _customer(db_session)
    intent = IntentMandate(
        customer_id=customer.id,
        raw_text="x",
        structured_json={"budget_paise": None},
        status="draft",
    )
    db_session.add(intent)
    db_session.commit()

    fake = _patch_client(monkeypatch, [_response(_message(content="ok"))])
    run_turn(db_session, MandateContext(customer_id=customer.id, intent_id=intent.id), "looks good")

    tool_names = {t["function"]["name"] for t in fake.calls[0]["tools"]}
    assert tool_names == {"propose_intent", "confirm_intent"}


def test_confirm_intent_via_tool_call_advances_to_building_cart(monkeypatch, db_session):
    customer = _customer(db_session)
    intent = IntentMandate(
        customer_id=customer.id, raw_text="x", structured_json={"budget_paise": None}, status="draft"
    )
    db_session.add(intent)
    db_session.commit()

    call = _tool_call("call_1", "confirm_intent", {})
    _patch_client(
        monkeypatch,
        [_response(_message(tool_calls=[call])), _response(_message(content="Confirmed."))],
    )

    result = run_turn(
        db_session, MandateContext(customer_id=customer.id, intent_id=intent.id), "yes confirm"
    )

    assert result.state == AgentState.BUILDING_CART
    db_session.refresh(intent)
    assert intent.status == "confirmed"


def test_confirm_intent_auto_chains_into_search_catalog_same_turn(monkeypatch, db_session):
    """The fix for "it stops after confirming and I have to prod it" — a
    non-mutating tool (search_catalog) can fire in the same turn right
    after confirm_intent, without a second user message, since state is
    re-derived between rounds and confirm_intent isn't callable again."""
    merchant = Merchant(name="M")
    db_session.add(merchant)
    db_session.flush()
    db_session.add(Product(merchant_id=merchant.id, name="Charger", description=None, price=79900, stock=5))
    customer = _customer(db_session)
    intent = IntentMandate(
        customer_id=customer.id, raw_text="x", structured_json={"budget_paise": None}, status="draft"
    )
    db_session.add(intent)
    db_session.commit()

    confirm_call = _tool_call("call_1", "confirm_intent", {})
    search_call = _tool_call("call_2", "search_catalog", {"query": "charger"})
    fake = _patch_client(
        monkeypatch,
        [
            _response(_message(tool_calls=[confirm_call])),
            _response(_message(tool_calls=[search_call])),
            _response(_message(content="Here's what I found.")),
        ],
    )

    result = run_turn(
        db_session, MandateContext(customer_id=customer.id, intent_id=intent.id), "yes confirm"
    )

    assert [tc["tool"] for tc in result.tool_calls] == ["confirm_intent", "search_catalog"]
    assert result.reply == "Here's what I found."
    assert result.state == AgentState.BUILDING_CART
    # second round's tool list must reflect the NEW state, not the old one
    assert {t["function"]["name"] for t in fake.calls[1]["tools"]} == {
        "search_catalog",
        "suggest_upsell",
        "accept_upsell",
        "decline_upsell",
        "propose_cart",
    }


def test_round_safety_valve_forces_a_reply_if_model_never_stops_calling_tools(monkeypatch, db_session):
    customer = _customer(db_session)
    intent = IntentMandate(
        customer_id=customer.id, raw_text="x", structured_json={"budget_paise": None}, status="draft"
    )
    db_session.add(intent)
    db_session.commit()

    # confirm_intent only exists once (state changes after), so pad with
    # search_catalog calls to simulate a model that just won't stop.
    responses = [_response(_message(tool_calls=[_tool_call("call_1", "confirm_intent", {})]))]
    for i in range(10):
        responses.append(
            _response(_message(tool_calls=[_tool_call(f"call_s{i}", "search_catalog", {"query": "x"})]))
        )
    _patch_client(monkeypatch, responses)

    result = run_turn(
        db_session, MandateContext(customer_id=customer.id, intent_id=intent.id), "yes confirm"
    )

    assert result.reply  # never crashes, never hangs, always produces something
    assert len(result.tool_calls) <= orchestrator_module.MAX_ROUNDS


def test_illegal_tool_call_is_rejected_not_executed(monkeypatch, db_session):
    """Defense in depth: even if the model emits a tool name not valid for
    the current state, it must not be dispatched."""
    call = _tool_call("call_1", "confirm_cart", {})  # not valid in DRAFTING_INTENT
    _patch_client(
        monkeypatch,
        [_response(_message(tool_calls=[call])), _response(_message(content="I can't do that yet."))],
    )

    result = run_turn(db_session, MandateContext(), "please pay now")

    assert result.tool_calls[0]["output"]["error"].startswith("'confirm_cart' is not available")
    assert result.state == AgentState.DRAFTING_INTENT


def test_building_cart_exposes_search_upsell_and_propose_cart(monkeypatch, db_session):
    customer = _customer(db_session, saved_address={"line1": "x"})
    intent = _confirmed_intent(db_session, customer)
    db_session.commit()

    fake = _patch_client(monkeypatch, [_response(_message(content="ok"))])
    run_turn(db_session, MandateContext(customer_id=customer.id, intent_id=intent.id), "show me options")

    tool_names = {t["function"]["name"] for t in fake.calls[0]["tools"]}
    assert tool_names == {"search_catalog", "suggest_upsell", "accept_upsell", "decline_upsell", "propose_cart"}


def test_search_catalog_tool_returns_matching_products(monkeypatch, db_session):
    merchant = Merchant(name="M")
    db_session.add(merchant)
    db_session.flush()
    product = Product(merchant_id=merchant.id, name="Power Bank", description=None, price=100000, stock=5)
    db_session.add(product)
    customer = _customer(db_session, saved_address={"line1": "x"})
    intent = _confirmed_intent(db_session, customer)
    db_session.commit()

    call = _tool_call("call_1", "search_catalog", {"query": "power"})
    _patch_client(
        monkeypatch,
        [_response(_message(tool_calls=[call])), _response(_message(content="Found one."))],
    )

    result = run_turn(
        db_session, MandateContext(customer_id=customer.id, intent_id=intent.id), "any power banks?"
    )

    assert result.tool_calls[0]["output"]["products"][0]["name"] == "Power Bank"


def test_propose_cart_advances_to_awaiting_cart_ok(monkeypatch, db_session):
    merchant = Merchant(name="M")
    db_session.add(merchant)
    db_session.flush()
    product = Product(merchant_id=merchant.id, name="Power Bank", description=None, price=100000, stock=5)
    db_session.add(product)
    db_session.flush()
    customer = _customer(db_session, saved_address={"line1": "x"})
    intent = _confirmed_intent(db_session, customer)
    db_session.commit()

    call = _tool_call("call_1", "propose_cart", {"items": [{"product_id": str(product.id), "quantity": 1}]})
    _patch_client(
        monkeypatch,
        [_response(_message(tool_calls=[call])), _response(_message(content="Here's your cart."))],
    )

    result = run_turn(
        db_session, MandateContext(customer_id=customer.id, intent_id=intent.id), "add the power bank"
    )

    assert result.state == AgentState.AWAITING_CART_OK
    assert result.context.cart_id is not None


def test_revising_draft_cart_adds_a_second_item(monkeypatch, db_session):
    merchant = Merchant(name="M")
    db_session.add(merchant)
    db_session.flush()
    charger = Product(merchant_id=merchant.id, name="Charger", description=None, price=79900, stock=5)
    phone_case = Product(merchant_id=merchant.id, name="Phone Case", description=None, price=39900, stock=5)
    db_session.add_all([charger, phone_case])
    db_session.flush()
    customer = _customer(db_session, saved_address={"line1": "x"})
    intent = _confirmed_intent(db_session, customer)
    cart = CartMandate(
        intent_mandate_id=intent.id,
        items=[{"product_id": str(charger.id), "name": "Charger", "unit_price": 79900, "quantity": 1, "line_total": 79900}],
        total_amount=84800,
        shipping_address={"line1": "x"},
        status="draft",
    )
    db_session.add(cart)
    db_session.commit()

    call = _tool_call(
        "call_1",
        "propose_cart",
        {"items": [{"product_id": str(charger.id), "quantity": 1}, {"product_id": str(phone_case.id), "quantity": 1}]},
    )
    _patch_client(
        monkeypatch,
        [_response(_message(tool_calls=[call])), _response(_message(content="Added the phone case too."))],
    )

    result = run_turn(
        db_session,
        MandateContext(customer_id=customer.id, intent_id=intent.id, cart_id=cart.id),
        "can you get me a phone case as well",
    )

    assert result.state == AgentState.AWAITING_CART_OK
    assert result.context.cart_id != cart.id  # superseded by a fresh draft
    assert len(result.tool_calls[0]["output"]["items"]) == 2


def test_suggest_upsell_returns_other_merchant_products(monkeypatch, db_session):
    merchant = Merchant(name="M")
    db_session.add(merchant)
    db_session.flush()
    main_item = Product(merchant_id=merchant.id, name="Power Bank", description=None, price=100000, stock=5)
    addon = Product(merchant_id=merchant.id, name="USB-C Cable", description="1m braided cable", price=29900, stock=10)
    db_session.add_all([main_item, addon])
    db_session.flush()
    customer = _customer(db_session, saved_address={"line1": "x"})
    intent = _confirmed_intent(db_session, customer)
    db_session.commit()

    call = _tool_call("call_1", "suggest_upsell", {"selected_product_ids": [str(main_item.id)]})
    _patch_client(
        monkeypatch,
        [_response(_message(tool_calls=[call])), _response(_message(content="Want a cable with that?"))],
    )

    result = run_turn(
        db_session, MandateContext(customer_id=customer.id, intent_id=intent.id), "just the power bank"
    )

    candidates = result.tool_calls[0]["output"]["candidates"]
    assert [c["name"] for c in candidates] == ["USB-C Cable"]
    assert result.state == AgentState.BUILDING_CART  # suggesting doesn't advance state


def test_accept_upsell_returns_product_details_for_next_propose_cart(monkeypatch, db_session):
    merchant = Merchant(name="M")
    db_session.add(merchant)
    db_session.flush()
    addon = Product(merchant_id=merchant.id, name="USB-C Cable", description=None, price=29900, stock=10)
    db_session.add(addon)
    db_session.flush()
    customer = _customer(db_session, saved_address={"line1": "x"})
    intent = _confirmed_intent(db_session, customer)
    db_session.commit()

    call = _tool_call("call_1", "accept_upsell", {"product_id": str(addon.id), "quantity": 1})
    _patch_client(
        monkeypatch,
        [_response(_message(tool_calls=[call])), _response(_message(content="Added the cable."))],
    )

    result = run_turn(db_session, MandateContext(customer_id=customer.id, intent_id=intent.id), "sure, add it")

    output = result.tool_calls[0]["output"]
    assert output["accepted"] is True
    assert output["product_id"] == str(addon.id)
    assert result.context.cart_id is None  # accepting doesn't itself create a cart


def test_accept_upsell_unknown_product_surfaces_as_error(monkeypatch, db_session):
    customer = _customer(db_session, saved_address={"line1": "x"})
    intent = _confirmed_intent(db_session, customer)
    db_session.commit()

    call = _tool_call("call_1", "accept_upsell", {"product_id": str(uuid.uuid4())})
    _patch_client(
        monkeypatch,
        [_response(_message(tool_calls=[call])), _response(_message(content="Hmm, let me check."))],
    )

    result = run_turn(db_session, MandateContext(customer_id=customer.id, intent_id=intent.id), "add it")

    assert "not found" in result.tool_calls[0]["output"]["error"]


def test_decline_upsell_acknowledges_without_side_effects(monkeypatch, db_session):
    customer = _customer(db_session, saved_address={"line1": "x"})
    intent = _confirmed_intent(db_session, customer)
    db_session.commit()

    call = _tool_call("call_1", "decline_upsell", {})
    _patch_client(
        monkeypatch,
        [_response(_message(tool_calls=[call])), _response(_message(content="No problem."))],
    )

    result = run_turn(db_session, MandateContext(customer_id=customer.id, intent_id=intent.id), "no thanks")

    assert result.tool_calls[0]["output"] == {"accepted": False}
    assert result.state == AgentState.BUILDING_CART


def test_awaiting_cart_ok_exposes_revision_tools_and_confirm(monkeypatch, db_session):
    """A draft (unconfirmed) cart can still be revised — search/upsell/
    propose_cart stay available alongside confirm_cart so "add a phone case
    too" before confirming isn't a dead end. The real guarantee (never add
    an upsell item after the cart is CONFIRMED) is enforced by these tools
    disappearing entirely once EXECUTING_PAYMENT begins, not by locking them
    out the moment a draft merely exists."""
    customer = _customer(db_session, saved_address={"line1": "x"})
    intent = _confirmed_intent(db_session, customer)
    cart = CartMandate(
        intent_mandate_id=intent.id,
        items=[],
        total_amount=10000,
        shipping_address={"line1": "x"},
        status="draft",
    )
    db_session.add(cart)
    db_session.commit()

    fake = _patch_client(monkeypatch, [_response(_message(content="ok"))])
    run_turn(
        db_session, MandateContext(customer_id=customer.id, intent_id=intent.id, cart_id=cart.id), "confirm it"
    )

    tool_names = {t["function"]["name"] for t in fake.calls[0]["tools"]}
    assert tool_names == {
        "search_catalog",
        "suggest_upsell",
        "accept_upsell",
        "decline_upsell",
        "propose_cart",
        "confirm_cart",
    }


def test_confirmed_cart_no_longer_exposes_revision_tools(monkeypatch, db_session):
    """Once the cart is actually confirmed, revision tools vanish for good —
    this is the guarantee that matters, not locking a mere draft."""
    customer = _customer(db_session, saved_address={"line1": "x"})
    intent = _confirmed_intent(db_session, customer)
    cart = CartMandate(
        intent_mandate_id=intent.id,
        items=[],
        total_amount=10000,
        shipping_address={"line1": "x"},
        status="confirmed",
        signature="s",
        confirmed_at=datetime.now(UTC),
    )
    db_session.add(cart)
    db_session.commit()

    fake = _patch_client(monkeypatch, [_response(_message(content="ok"))])
    run_turn(
        db_session, MandateContext(customer_id=customer.id, intent_id=intent.id, cart_id=cart.id), "add one more"
    )

    tool_names = {t["function"]["name"] for t in fake.calls[0]["tools"]}
    assert "propose_cart" not in tool_names
    assert "suggest_upsell" not in tool_names


def test_confirm_cart_budget_guard_surfaces_as_tool_error_not_crash(monkeypatch, db_session):
    customer = _customer(db_session, saved_address={"line1": "x"})
    intent = _confirmed_intent(db_session, customer, budget_paise=10000)
    cart = CartMandate(
        intent_mandate_id=intent.id,
        items=[],
        total_amount=99999,
        shipping_address={"line1": "x"},
        status="draft",
    )
    db_session.add(cart)
    db_session.commit()

    call = _tool_call("call_1", "confirm_cart", {})
    _patch_client(
        monkeypatch,
        [_response(_message(tool_calls=[call])), _response(_message(content="That's over budget."))],
    )

    result = run_turn(
        db_session,
        MandateContext(customer_id=customer.id, intent_id=intent.id, cart_id=cart.id),
        "confirm it",
    )

    assert "exceeds intent budget" in result.tool_calls[0]["output"]["error"]
    assert result.state == AgentState.AWAITING_CART_OK
    db_session.refresh(cart)
    assert cart.status == "draft"


def test_executing_payment_exposes_create_and_check(monkeypatch, db_session):
    customer = _customer(db_session, saved_address={"line1": "x"})
    intent = _confirmed_intent(db_session, customer)
    cart = CartMandate(
        intent_mandate_id=intent.id,
        items=[],
        total_amount=10000,
        shipping_address={"line1": "x"},
        status="confirmed",
        signature="s",
        confirmed_at=datetime.now(UTC),
    )
    db_session.add(cart)
    db_session.commit()

    fake = _patch_client(monkeypatch, [_response(_message(content="ok"))])
    run_turn(
        db_session, MandateContext(customer_id=customer.id, intent_id=intent.id, cart_id=cart.id), "pay now"
    )

    tool_names = {t["function"]["name"] for t in fake.calls[0]["tools"]}
    assert tool_names == {"create_payment", "check_payment_status"}


def test_create_payment_tool_dispatches_to_adapter(monkeypatch, db_session):
    class FakeProvider:
        def create_charge(self, amount, currency, notes):
            return ChargeResult(
                reference="order_fake",
                adapter="standard_checkout",
                client_payload={"order_id": "order_fake", "key_id": "k", "amount": amount, "currency": currency},
            )

        def verify(self, payload):
            return True

    monkeypatch.setattr("app.services.payment_mandate.StandardCheckoutAdapter", FakeProvider)

    customer = _customer(db_session, saved_address={"line1": "x"})
    intent = _confirmed_intent(db_session, customer)
    cart = CartMandate(
        intent_mandate_id=intent.id,
        items=[],
        total_amount=10000,
        shipping_address={"line1": "x"},
        status="confirmed",
        signature="s",
        confirmed_at=datetime.now(UTC),
    )
    db_session.add(cart)
    db_session.commit()

    call = _tool_call("call_1", "create_payment", {})
    _patch_client(
        monkeypatch,
        [_response(_message(tool_calls=[call])), _response(_message(content="Here's your payment link."))],
    )

    result = run_turn(
        db_session, MandateContext(customer_id=customer.id, intent_id=intent.id, cart_id=cart.id), "pay now"
    )

    assert result.context.payment_id is not None
    assert result.tool_calls[0]["output"]["client_payload"]["order_id"] == "order_fake"
    assert result.state == AgentState.EXECUTING_PAYMENT


def test_terminal_state_exposes_only_check_payment_status(monkeypatch, db_session):
    """Regression test: check_payment_status must survive into TERMINAL.
    The async webhook can flip pending -> executed *after* the model's last
    real information, and a customer asking "did it go through?" right at
    that moment needs a grounded answer, not a hallucinated one from a model
    with zero tools left to verify against."""
    from app.models import PaymentMandate

    customer = _customer(db_session, saved_address={"line1": "x"})
    intent = _confirmed_intent(db_session, customer)
    cart = CartMandate(
        intent_mandate_id=intent.id,
        items=[],
        total_amount=10000,
        shipping_address={"line1": "x"},
        status="confirmed",
        signature="s",
        confirmed_at=datetime.now(UTC),
    )
    db_session.add(cart)
    db_session.flush()
    payment = PaymentMandate(cart_mandate_id=cart.id, amount=10000, status="executed")
    db_session.add(payment)
    db_session.commit()

    fake = _patch_client(monkeypatch, [_response(_message(content="All done!"))])
    result = run_turn(
        db_session,
        MandateContext(customer_id=customer.id, intent_id=intent.id, cart_id=cart.id, payment_id=payment.id),
        "thanks",
    )

    tool_names = {t["function"]["name"] for t in fake.calls[0]["tools"]}
    assert tool_names == {"check_payment_status"}
    assert result.state == AgentState.TERMINAL


def test_asking_did_it_go_through_after_terminal_gets_a_grounded_answer(monkeypatch, db_session):
    """The exact bug reported live: webhook resolves the payment to executed,
    then the customer asks "did my payment go through?" — the model must
    actually call check_payment_status and report the real status, not
    restate stale "pending" from earlier in the conversation."""
    from app.models import PaymentMandate

    customer = _customer(db_session, saved_address={"line1": "x"})
    intent = _confirmed_intent(db_session, customer)
    cart = CartMandate(
        intent_mandate_id=intent.id,
        items=[],
        total_amount=10000,
        shipping_address={"line1": "x"},
        status="confirmed",
        signature="s",
        confirmed_at=datetime.now(UTC),
    )
    db_session.add(cart)
    db_session.flush()
    payment = PaymentMandate(
        cart_mandate_id=cart.id, amount=10000, status="executed", razorpay_payment_id="pay_x"
    )
    db_session.add(payment)
    db_session.commit()

    call = _tool_call("call_1", "check_payment_status", {})
    _patch_client(
        monkeypatch,
        [
            _response(_message(tool_calls=[call])),
            _response(_message(content="Good news — your payment went through successfully!")),
        ],
    )
    result = run_turn(
        db_session,
        MandateContext(customer_id=customer.id, intent_id=intent.id, cart_id=cart.id, payment_id=payment.id),
        "did my payment go through?",
    )

    assert result.tool_calls[0]["tool"] == "check_payment_status"
    assert result.tool_calls[0]["output"]["status"] == "executed"
    assert result.state == AgentState.TERMINAL


def test_new_messages_thread_full_tool_round_for_history(monkeypatch, db_session):
    """The caller must be able to reconstruct correct multi-turn context by
    appending new_messages verbatim — dropping tool results (e.g. keeping
    only the reply text) loses details like exact product ids."""
    call = _tool_call("call_1", "search_catalog", {"query": "earbuds"})
    _patch_client(
        monkeypatch,
        [_response(_message(tool_calls=[call])), _response(_message(content="Here's what we found."))],
    )
    customer = _customer(db_session, saved_address={"line1": "x"})
    intent = _confirmed_intent(db_session, customer)
    db_session.commit()

    result = run_turn(
        db_session, MandateContext(customer_id=customer.id, intent_id=intent.id), "any earbuds?"
    )

    roles = [m["role"] for m in result.new_messages]
    assert roles == ["user", "assistant", "tool", "assistant"]
    assert result.new_messages[0]["content"] == "any earbuds?"
    assert result.new_messages[2]["tool_call_id"] == "call_1"
    assert json.loads(result.new_messages[2]["content"])["products"] == []
    assert result.new_messages[-1]["content"] == "Here's what we found."


def test_new_messages_for_plain_reply_has_no_tool_messages(monkeypatch, db_session):
    _patch_client(monkeypatch, [_response(_message(content="Tell me more."))])

    result = run_turn(db_session, MandateContext(), "hi")

    assert [m["role"] for m in result.new_messages] == ["user", "assistant"]


def test_fallback_reply_used_when_model_returns_empty_summary(monkeypatch, db_session):
    """Some OpenRouter backends occasionally return empty content on the
    post-tool-call summary completion — never surface that as an empty
    reply to the human."""
    call = _tool_call("call_1", "confirm_intent", {})
    customer = _customer(db_session)
    intent = IntentMandate(
        customer_id=customer.id, raw_text="x", structured_json={"budget_paise": None}, status="draft"
    )
    db_session.add(intent)
    db_session.commit()
    _patch_client(monkeypatch, [_response(_message(tool_calls=[call])), _response(_message(content=""))])

    result = run_turn(
        db_session, MandateContext(customer_id=customer.id, intent_id=intent.id), "confirm"
    )

    assert result.reply == "confirm_intent completed."


def test_first_completion_returning_no_choices_falls_back_gracefully(monkeypatch, db_session):
    """Observed live: OpenRouter occasionally returns choices=None instead of
    raising. Must never surface as a 500 — nothing was persisted yet, so a
    graceful in-band reply (retry by just asking again) is the right outcome."""
    _patch_client(monkeypatch, [_empty_response(), _empty_response()])

    result = run_turn(db_session, MandateContext(), "I want some earbuds")

    assert "trouble reaching" in result.reply
    assert result.tool_calls == []
    assert result.state == AgentState.DRAFTING_INTENT


def test_first_completion_retries_once_before_giving_up(monkeypatch, db_session):
    fake = _patch_client(
        monkeypatch, [_empty_response(), _response(_message(content="Tell me more."))]
    )

    result = run_turn(db_session, MandateContext(), "I want some earbuds")

    assert len(fake.calls) == 2
    assert result.reply == "Tell me more."


def test_final_summary_completion_returning_no_choices_uses_fallback_reply(monkeypatch, db_session):
    call = _tool_call("call_1", "confirm_intent", {})
    customer = _customer(db_session)
    intent = IntentMandate(
        customer_id=customer.id, raw_text="x", structured_json={"budget_paise": None}, status="draft"
    )
    db_session.add(intent)
    db_session.commit()
    _patch_client(
        monkeypatch, [_response(_message(tool_calls=[call])), _empty_response(), _empty_response()]
    )

    result = run_turn(
        db_session, MandateContext(customer_id=customer.id, intent_id=intent.id), "confirm"
    )

    assert result.reply == "confirm_intent completed."
    # unlike the first-completion failure, the tool itself still ran
    assert result.state == AgentState.BUILDING_CART


def _confirmed_cart(db_session, intent, total_amount=10000) -> CartMandate:
    cart = CartMandate(
        intent_mandate_id=intent.id,
        items=[],
        total_amount=total_amount,
        shipping_address={"line1": "x"},
        status="confirmed",
        signature="s",
        confirmed_at=datetime.now(UTC),
    )
    db_session.add(cart)
    db_session.commit()
    return cart


def _failed_payment(db_session, cart, amount=10000) -> PaymentMandate:
    payment = PaymentMandate(cart_mandate_id=cart.id, razorpay_ref="order_old", amount=amount, status="failed")
    db_session.add(payment)
    db_session.commit()
    return payment


def test_payment_failed_exposes_retry_cancel_and_check_status(monkeypatch, db_session):
    customer = _customer(db_session, saved_address={"line1": "x"})
    intent = _confirmed_intent(db_session, customer)
    cart = _confirmed_cart(db_session, intent)
    payment = _failed_payment(db_session, cart)

    fake = _patch_client(
        monkeypatch, [_response(_message(content="Your payment didn't go through. Retry or cancel?"))]
    )
    result = run_turn(
        db_session,
        MandateContext(customer_id=customer.id, intent_id=intent.id, cart_id=cart.id, payment_id=payment.id),
        "what happened?",
    )

    tool_names = {t["function"]["name"] for t in fake.calls[0]["tools"]}
    assert tool_names == {"retry_payment", "cancel_payment", "check_payment_status"}
    assert result.state == AgentState.PAYMENT_FAILED


def test_retry_payment_creates_new_attempt_and_returns_to_executing(monkeypatch, db_session):
    class FakeProvider:
        def create_charge(self, amount, currency, notes):
            return ChargeResult(
                reference="order_retry",
                adapter="standard_checkout",
                client_payload={"order_id": "order_retry", "key_id": "k", "amount": amount, "currency": currency},
            )

        def verify(self, payload):
            return True

    monkeypatch.setattr("app.services.payment_mandate.StandardCheckoutAdapter", FakeProvider)

    customer = _customer(db_session, saved_address={"line1": "x"})
    intent = _confirmed_intent(db_session, customer)
    cart = _confirmed_cart(db_session, intent)
    old_payment = _failed_payment(db_session, cart)

    call = _tool_call("call_1", "retry_payment", {})
    _patch_client(
        monkeypatch,
        [_response(_message(tool_calls=[call])), _response(_message(content="Here's a fresh payment link."))],
    )

    result = run_turn(
        db_session,
        MandateContext(customer_id=customer.id, intent_id=intent.id, cart_id=cart.id, payment_id=old_payment.id),
        "let's try again",
    )

    assert result.context.payment_id != old_payment.id
    assert result.tool_calls[0]["output"]["client_payload"]["order_id"] == "order_retry"
    assert result.state == AgentState.EXECUTING_PAYMENT


def test_cancel_payment_tool_moves_to_terminal(monkeypatch, db_session):
    customer = _customer(db_session, saved_address={"line1": "x"})
    intent = _confirmed_intent(db_session, customer)
    cart = _confirmed_cart(db_session, intent)
    payment = _failed_payment(db_session, cart)

    call = _tool_call("call_1", "cancel_payment", {})
    _patch_client(
        monkeypatch,
        [_response(_message(tool_calls=[call])), _response(_message(content="Cancelled, no problem."))],
    )

    result = run_turn(
        db_session,
        MandateContext(customer_id=customer.id, intent_id=intent.id, cart_id=cart.id, payment_id=payment.id),
        "let's cancel",
    )

    assert result.tool_calls[0]["output"]["status"] == "cancelled"
    assert result.state == AgentState.TERMINAL
    db_session.refresh(payment)
    assert payment.status == "cancelled"


def test_propose_cart_price_rise_guard_surfaces_as_tool_error(monkeypatch, db_session):
    merchant = Merchant(name="M")
    db_session.add(merchant)
    db_session.flush()
    product = Product(merchant_id=merchant.id, name="Power Bank", description=None, price=10000, stock=5)
    db_session.add(product)
    db_session.flush()
    db_session.add(PriceHistory(product_id=product.id, price=10000))
    db_session.commit()
    record_price_change(db_session, product.id, 15000)  # +50%

    customer = _customer(db_session, saved_address={"line1": "x"})
    intent = _confirmed_intent(db_session, customer)
    db_session.commit()

    call = _tool_call("call_1", "propose_cart", {"items": [{"product_id": str(product.id), "quantity": 1}]})
    _patch_client(
        monkeypatch,
        [_response(_message(tool_calls=[call])), _response(_message(content="Price changed, heads up."))],
    )

    result = run_turn(
        db_session, MandateContext(customer_id=customer.id, intent_id=intent.id), "add the power bank"
    )

    assert "risen" in result.tool_calls[0]["output"]["error"]
    assert result.state == AgentState.BUILDING_CART  # not advanced
    assert result.context.cart_id is None
