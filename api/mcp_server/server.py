"""MCP server for the Claude Desktop surface (CLAUDE.md §4, §11 P3.2).

Exposes the same underlying service functions the website's REST routers
and orchestrator already call — no duplicate business logic. This is a
separate, purpose-built, buyer-scoped server: it is NOT Razorpay's own
official MCP server (§6.11), which is a merchant-ops tool authenticated
with full account access and has no concept of a catalog, cart, or mandate
at all. Nothing here reaches outside this app's own catalog/mandate/payment
services.

Claude Desktop has no browser (§6.5), so payment collection here goes
through PaymentLinkAdapter — a hosted URL Claude can hand back as a plain
clickable link — instead of StandardCheckoutAdapter's embedded widget.

Unlike app/orchestrator/, which drives our own OpenRouter model through a
turn-by-turn tool-calling loop with per-state tool *exposure* (CLAUDE.md
§7), this server hands tools directly to Claude Desktop's own model, which
does its own orchestration and remembers mandate ids across turns the
normal MCP way (via its conversation, the same way it remembers any other
tool result). MCP's tool list isn't turn-by-turn dynamic the way our
in-process loop is, so gating here is enforced the same place it always
was underneath the orchestrator too: every service function below already
rejects an out-of-order call with a clear LookupError/ValueError
(confirm_intent won't confirm a non-draft intent, create_payment_for_cart
won't charge an unconfirmed cart, etc.) — that's structural, not prompted,
regardless of which surface is calling it.
"""

import uuid
from contextlib import contextmanager

from mcp.server.fastmcp import FastMCP

from app.adapters.payment_link import PaymentLinkAdapter
from app.db import SessionLocal
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

mcp = FastMCP(
    "ap2-agentic-commerce",
    instructions=(
        "Guide the customer through: propose_intent -> confirm_intent -> "
        "search_catalog/propose_cart -> confirm_cart -> create_payment_link -> "
        "check_payment_status. Always get explicit human confirmation before "
        "confirm_intent and confirm_cart — never skip ahead on the model's own "
        "judgment. search_catalog spans every merchant; when the same or a "
        "similar product appears from more than one, point that out and "
        "recommend the cheapest unless the customer prefers a specific "
        "merchant. Before finalizing the cart, consider suggest_upsell once — "
        "at most one relevant add-on, zero pressure if declined, never raised "
        "again after propose_cart. If a payment fails, say so plainly and "
        "offer retry_payment or cancel_payment — never go silent."
    ),
)


@contextmanager
def _db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@mcp.tool()
def propose_intent(
    product_query: str,
    quantity: int = 1,
    budget_paise: int | None = None,
    constraints: list[str] | None = None,
    customer_id: str | None = None,
) -> dict:
    """Draft a structured purchase intent. Must be confirmed by the human (confirm_intent) before searching the catalog."""
    with _db() as db:
        structured = IntentExtraction(
            product_query=product_query,
            quantity=quantity,
            budget_paise=budget_paise,
            constraints=constraints or [],
        )
        mandate = create_draft_intent_from_structured(
            db, uuid.UUID(customer_id) if customer_id else None, product_query, structured
        )
        return {"intent_id": str(mandate.id), "status": mandate.status, "structured": mandate.structured_json}


@mcp.tool()
def confirm_intent(intent_id: str) -> dict:
    """Confirm a draft intent after the human has reviewed it. Signs it and makes it immutable."""
    with _db() as db:
        try:
            mandate = confirm_intent_service(db, uuid.UUID(intent_id))
        except (LookupError, ValueError) as e:
            return {"error": str(e)}
        return {"intent_id": str(mandate.id), "status": mandate.status, "signature": mandate.signature}


@mcp.tool()
def search_catalog(query: str) -> dict:
    """Search across ALL merchants' catalogs for products matching a query. Results may include the same or a similar product from multiple merchants at different prices — when they do, point that out and recommend the cheapest one unless the customer has stated another preference."""
    with _db() as db:
        products = SqlAlchemyCatalogRepository(db).search(query)
        return {
            "products": [
                {
                    "id": str(p.id),
                    "name": p.name,
                    "price": p.price,
                    "description": p.description,
                    "merchant_id": str(p.merchant_id),
                    "merchant_name": p.merchant_name,
                }
                for p in products
            ]
        }


@mcp.tool()
def suggest_upsell(selected_product_ids: list[str]) -> dict:
    """Look up complementary products from the same merchant, excluding what the customer already picked. Call once before propose_cart; skip if nothing relevant comes back."""
    with _db() as db:
        candidates = suggest_upsell_candidates(db, [uuid.UUID(pid) for pid in selected_product_ids])
        return {
            "candidates": [
                {"id": str(p.id), "name": p.name, "price": p.price, "description": p.description}
                for p in candidates
            ]
        }


@mcp.tool()
def accept_upsell(product_id: str, quantity: int = 1) -> dict:
    """Record that the customer agreed to add the suggested upsell item. Include its product_id in the items list of the propose_cart call that follows."""
    with _db() as db:
        product = SqlAlchemyCatalogRepository(db).get_product(uuid.UUID(product_id))
        if product is None:
            return {"error": f"product {product_id} not found"}
        return {
            "accepted": True,
            "product_id": str(product.id),
            "name": product.name,
            "price": product.price,
            "quantity": quantity,
        }


@mcp.tool()
def decline_upsell() -> dict:
    """Record that the customer declined the suggested upsell. Proceed to propose_cart without it."""
    return {"accepted": False}


@mcp.tool()
def propose_cart(
    intent_mandate_id: str,
    items: list[dict],
    shipping_address: dict | None = None,
    acknowledge_price_change: bool = False,
) -> dict:
    """Assemble a cart from catalog items for the confirmed intent. Each item is {"product_id": str, "quantity": int}. shipping_address may be omitted if the customer has one on file."""
    with _db() as db:
        request = CartDraftRequest(
            intent_mandate_id=uuid.UUID(intent_mandate_id),
            items=[CartItemRequest(**item) for item in items],
            shipping_address=shipping_address,
            acknowledge_price_change=acknowledge_price_change,
        )
        try:
            cart = create_draft_cart(db, request)
        except (LookupError, ValueError) as e:
            return {"error": str(e)}
        return {
            "cart_id": str(cart.id),
            "items": cart.items,
            "total_amount": cart.total_amount,
            "shipping_address": cart.shipping_address,
            "status": cart.status,
        }


@mcp.tool()
def confirm_cart(cart_id: str) -> dict:
    """Confirm the current draft cart after the human has reviewed items, total, and address."""
    with _db() as db:
        try:
            cart = confirm_cart_service(db, uuid.UUID(cart_id))
        except (LookupError, ValueError) as e:
            return {"error": str(e)}
        return {"cart_id": str(cart.id), "status": cart.status, "total_amount": cart.total_amount}


@mcp.tool()
def create_payment_link(cart_id: str) -> dict:
    """Create a hosted Razorpay Payment Link for the confirmed cart and return its URL — present this to the customer as a clickable link, since there's no browser here to open a checkout widget."""
    with _db() as db:
        try:
            payment, charge = create_payment_for_cart(db, uuid.UUID(cart_id), provider=PaymentLinkAdapter())
        except (LookupError, ValueError) as e:
            return {"error": str(e)}
        return {
            "payment_id": str(payment.id),
            "status": payment.status,
            "payment_link_url": charge.client_payload["short_url"],
        }


@mcp.tool()
def check_payment_status(payment_id: str) -> dict:
    """Check whether the payment has been confirmed by the payment provider yet."""
    with _db() as db:
        payment = get_payment_mandate(db, uuid.UUID(payment_id))
        if payment is None:
            return {"error": "payment mandate not found"}
        return {"status": payment.status, "razorpay_payment_id": payment.razorpay_payment_id}


@mcp.tool()
def retry_payment(cart_id: str) -> dict:
    """After a payment failure, start a new Payment Link for the same confirmed cart."""
    return create_payment_link(cart_id)


@mcp.tool()
def cancel_payment(payment_id: str) -> dict:
    """After a payment failure, cancel the transaction instead of retrying."""
    with _db() as db:
        try:
            payment = cancel_payment_service(db, uuid.UUID(payment_id))
        except (LookupError, ValueError) as e:
            return {"error": str(e)}
        return {"payment_id": str(payment.id), "status": payment.status}


if __name__ == "__main__":
    mcp.run(transport="stdio")
