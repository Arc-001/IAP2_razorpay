"""Tool registry, keyed by AgentState (CLAUDE.md §7). Each handler wraps an
existing service function — the orchestrator adds no new business logic,
only exposure gating and dispatch. The model is never trusted with mandate
ids as arguments; ids live in MandateContext and flow through the loop.

Deliberately not yet implemented: revise_intent, revise_cart — scoped out
of SCRUM-18/19 (the fix is to re-draft). Adding either later is one
registry entry, not a redesign.

suggest_upsell/accept_upsell/decline_upsell (SCRUM-27) are registered under
BUILDING_CART, not AWAITING_CART_OK as CLAUDE.md §7's table literally lists
them. That table's own prose guard is more specific and takes precedence:
"suggest_upsell must resolve ... before the state moves to AWAITING_CART_OK."
There's no sessions table (state.py) to persist "an upsell was offered and
is pending" across a state boundary, so the only way to make that guard
structural rather than prompted is to keep all three tools — and therefore
the whole offer/accept/decline exchange — inside BUILDING_CART, before
propose_cart ever creates the draft cart row. This also gives the stronger,
explicitly-required guarantee for free: since none of the three tools are
reachable once a cart exists, an upsell item can structurally never be
added after the cart is confirmed (or even just drafted).
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace

from sqlalchemy.orm import Session

from app.orchestrator.context import MandateContext, ToolResult
from app.orchestrator.state import AgentState
from app.repositories.catalog import SqlAlchemyCatalogRepository
from app.schemas.cart import CartDraftRequest, CartItemRequest
from app.schemas.intent import IntentExtraction
from app.services.cart_mandate import confirm_cart as confirm_cart_service
from app.services.cart_mandate import create_draft_cart
from app.services.intent_mandate import confirm_intent as confirm_intent_service
from app.services.intent_mandate import create_draft_intent_from_structured
from app.services.payment_mandate import cancel_payment as cancel_payment_service
from app.services.payment_mandate import create_payment_for_cart, get_payment_mandate
from app.services.upsell import suggest_upsell_candidates

ToolHandler = Callable[[Session, MandateContext, dict, str], ToolResult]


@dataclass(frozen=True)
class ToolDef:
    schema: dict
    handler: ToolHandler


def _propose_intent(db: Session, ctx: MandateContext, args: dict, user_message: str) -> ToolResult:
    structured = IntentExtraction(**args)
    mandate = create_draft_intent_from_structured(db, ctx.customer_id, user_message, structured)
    return ToolResult(
        output={"id": str(mandate.id), "status": mandate.status, "structured": mandate.structured_json},
        context=replace(ctx, intent_id=mandate.id),
    )


def _confirm_intent(db: Session, ctx: MandateContext, args: dict, user_message: str) -> ToolResult:
    mandate = confirm_intent_service(db, ctx.intent_id)
    return ToolResult(output={"status": mandate.status, "signature": mandate.signature}, context=ctx)


def _search_catalog(db: Session, ctx: MandateContext, args: dict, user_message: str) -> ToolResult:
    products = SqlAlchemyCatalogRepository(db).search(args["query"])
    output = {
        "products": [
            {"id": str(p.id), "name": p.name, "price": p.price, "description": p.description}
            for p in products
        ]
    }
    return ToolResult(output=output, context=ctx)


def _suggest_upsell(db: Session, ctx: MandateContext, args: dict, user_message: str) -> ToolResult:
    selected_ids = [uuid.UUID(pid) for pid in args.get("selected_product_ids", [])]
    candidates = suggest_upsell_candidates(db, selected_ids)
    output = {
        "candidates": [
            {"id": str(p.id), "name": p.name, "price": p.price, "description": p.description}
            for p in candidates
        ]
    }
    return ToolResult(output=output, context=ctx)


def _accept_upsell(db: Session, ctx: MandateContext, args: dict, user_message: str) -> ToolResult:
    product = SqlAlchemyCatalogRepository(db).get_product(uuid.UUID(args["product_id"]))
    if product is None:
        return ToolResult(output={"error": f"product {args['product_id']} not found"}, context=ctx)
    return ToolResult(
        output={
            "accepted": True,
            "product_id": str(product.id),
            "name": product.name,
            "price": product.price,
            "quantity": args.get("quantity", 1),
        },
        context=ctx,
    )


def _decline_upsell(db: Session, ctx: MandateContext, args: dict, user_message: str) -> ToolResult:
    return ToolResult(output={"accepted": False}, context=ctx)


def _propose_cart(db: Session, ctx: MandateContext, args: dict, user_message: str) -> ToolResult:
    request = CartDraftRequest(
        intent_mandate_id=ctx.intent_id,
        items=[CartItemRequest(**item) for item in args["items"]],
        shipping_address=args.get("shipping_address"),
        acknowledge_price_change=args.get("acknowledge_price_change", False),
    )
    cart = create_draft_cart(db, request)
    return ToolResult(
        output={
            "id": str(cart.id),
            "items": cart.items,
            "total_amount": cart.total_amount,
            "shipping_address": cart.shipping_address,
            "status": cart.status,
        },
        context=replace(ctx, cart_id=cart.id),
    )


def _confirm_cart(db: Session, ctx: MandateContext, args: dict, user_message: str) -> ToolResult:
    cart = confirm_cart_service(db, ctx.cart_id)
    return ToolResult(
        output={"status": cart.status, "signature": cart.signature, "total_amount": cart.total_amount},
        context=ctx,
    )


def _create_payment(db: Session, ctx: MandateContext, args: dict, user_message: str) -> ToolResult:
    payment, charge = create_payment_for_cart(db, ctx.cart_id)
    return ToolResult(
        output={"id": str(payment.id), "status": payment.status, "client_payload": charge.client_payload},
        context=replace(ctx, payment_id=payment.id),
    )


def _retry_payment(db: Session, ctx: MandateContext, args: dict, user_message: str) -> ToolResult:
    """Same underlying operation as create_payment — a retry is just a new
    payment attempt against the same (still-confirmed) cart. Distinct tool
    name/description so the model reaches for it specifically after a
    failure rather than re-deriving the same call."""
    payment, charge = create_payment_for_cart(db, ctx.cart_id)
    return ToolResult(
        output={"id": str(payment.id), "status": payment.status, "client_payload": charge.client_payload},
        context=replace(ctx, payment_id=payment.id),
    )


def _cancel_payment(db: Session, ctx: MandateContext, args: dict, user_message: str) -> ToolResult:
    payment = cancel_payment_service(db, ctx.payment_id)
    return ToolResult(output={"status": payment.status}, context=ctx)


def _check_payment_status(db: Session, ctx: MandateContext, args: dict, user_message: str) -> ToolResult:
    payment = get_payment_mandate(db, ctx.payment_id)
    if payment is None:
        return ToolResult(output={"error": "payment mandate not found"}, context=ctx)
    return ToolResult(
        output={"status": payment.status, "razorpay_payment_id": payment.razorpay_payment_id}, context=ctx
    )


_PROPOSE_INTENT = ToolDef(
    schema={
        "type": "function",
        "function": {
            "name": "propose_intent",
            "description": "Propose a structured purchase intent extracted from the customer's request.",
            "parameters": IntentExtraction.model_json_schema(),
        },
    },
    handler=_propose_intent,
)

_CONFIRM_INTENT = ToolDef(
    schema={
        "type": "function",
        "function": {
            "name": "confirm_intent",
            "description": "Confirm the current draft intent after the human has reviewed it.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    handler=_confirm_intent,
)

_SEARCH_CATALOG = ToolDef(
    schema={
        "type": "function",
        "function": {
            "name": "search_catalog",
            "description": "Search the merchant catalog for products matching a query.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    handler=_search_catalog,
)

_SUGGEST_UPSELL = ToolDef(
    schema={
        "type": "function",
        "function": {
            "name": "suggest_upsell",
            "description": (
                "Look up complementary products from the same merchant that the customer hasn't "
                "already selected. Call this once, after the customer's main items are decided but "
                "before propose_cart, to consider offering ONE relevant add-on. If it returns no "
                "candidates, or none are genuinely relevant, skip straight to propose_cart — don't "
                "force a suggestion."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "selected_product_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Product ids the customer has already chosen, so they aren't re-suggested.",
                    }
                },
                "required": ["selected_product_ids"],
            },
        },
    },
    handler=_suggest_upsell,
)

_ACCEPT_UPSELL = ToolDef(
    schema={
        "type": "function",
        "function": {
            "name": "accept_upsell",
            "description": (
                "Record that the customer agreed to add the suggested upsell item. Include its "
                "product_id in the items list of the propose_cart call that follows."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string"},
                    "quantity": {"type": "integer", "minimum": 1, "default": 1},
                },
                "required": ["product_id"],
            },
        },
    },
    handler=_accept_upsell,
)

_DECLINE_UPSELL = ToolDef(
    schema={
        "type": "function",
        "function": {
            "name": "decline_upsell",
            "description": "Record that the customer declined the suggested upsell. Proceed to propose_cart without it — no pressure, no re-asking.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    handler=_decline_upsell,
)

_PROPOSE_CART = ToolDef(
    schema={
        "type": "function",
        "function": {
            "name": "propose_cart",
            "description": "Assemble a cart from catalog items for the confirmed intent.",
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "product_id": {"type": "string"},
                                "quantity": {"type": "integer", "minimum": 1},
                            },
                            "required": ["product_id", "quantity"],
                        },
                    },
                    "shipping_address": {
                        "type": "object",
                        "description": "Omit if the customer already has a saved address on file.",
                    },
                    "acknowledge_price_change": {
                        "type": "boolean",
                        "description": (
                            "Only set true after you've told the customer a product's price has "
                            "risen since it was last known and they've explicitly agreed to the "
                            "new price. The first attempt will fail with the old/new prices if "
                            "this is needed — relay that to the customer before retrying."
                        ),
                    },
                },
                "required": ["items"],
            },
        },
    },
    handler=_propose_cart,
)

_CONFIRM_CART = ToolDef(
    schema={
        "type": "function",
        "function": {
            "name": "confirm_cart",
            "description": "Confirm the current draft cart after the human has reviewed items, total, and address.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    handler=_confirm_cart,
)

_CREATE_PAYMENT = ToolDef(
    schema={
        "type": "function",
        "function": {
            "name": "create_payment",
            "description": "Create the payment for the confirmed cart and return checkout details.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    handler=_create_payment,
)

_CHECK_PAYMENT_STATUS = ToolDef(
    schema={
        "type": "function",
        "function": {
            "name": "check_payment_status",
            "description": "Check whether the payment has been confirmed by the payment provider yet.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    handler=_check_payment_status,
)

_RETRY_PAYMENT = ToolDef(
    schema={
        "type": "function",
        "function": {
            "name": "retry_payment",
            "description": "After a payment failure, start a new payment attempt for the same confirmed cart.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    handler=_retry_payment,
)

_CANCEL_PAYMENT = ToolDef(
    schema={
        "type": "function",
        "function": {
            "name": "cancel_payment",
            "description": "After a payment failure, cancel the transaction instead of retrying.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    handler=_cancel_payment,
)

TOOLS_BY_STATE: dict[AgentState, list[ToolDef]] = {
    AgentState.DRAFTING_INTENT: [_PROPOSE_INTENT],
    AgentState.AWAITING_INTENT_OK: [_CONFIRM_INTENT],
    AgentState.BUILDING_CART: [_SEARCH_CATALOG, _SUGGEST_UPSELL, _ACCEPT_UPSELL, _DECLINE_UPSELL, _PROPOSE_CART],
    AgentState.AWAITING_CART_OK: [_CONFIRM_CART],
    AgentState.EXECUTING_PAYMENT: [_CREATE_PAYMENT, _CHECK_PAYMENT_STATUS],
    AgentState.PAYMENT_FAILED: [_RETRY_PAYMENT, _CANCEL_PAYMENT],
    AgentState.TERMINAL: [],
}


def get_tools_for_state(state: AgentState) -> list[ToolDef]:
    return TOOLS_BY_STATE.get(state, [])


def get_tool(state: AgentState, name: str) -> ToolDef | None:
    return next((t for t in get_tools_for_state(state) if t.schema["function"]["name"] == name), None)
