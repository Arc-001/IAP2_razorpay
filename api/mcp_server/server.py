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

Transport: streamable-http, not stdio — see plan "MCP server: stdio ->
remote (streamable-http) transport". Every HTTP request is authenticated by
mcp_server/auth.py's BearerAuthMiddleware using the exact same login token
`/api/auth/login` issues — no separate auth infra, no free-form customer_id
tool argument. propose_intent reads the caller's customer_id off the
verified token (via Context), never from a parameter the model could get
wrong or a malicious caller could spoof. Bind stays 127.0.0.1 until the
deploy step puts nginx/TLS in front of it.
"""

import logging
import os
import uuid
from contextlib import contextmanager

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.transport_security import TransportSecuritySettings

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
    host=os.environ.get("MCP_HOST", "127.0.0.1"),
    port=int(os.environ.get("MCP_PORT", "8124")),
    # The SDK's default DNS-rebinding protection only accepts a localhost-shaped
    # Host header, which rejects every request that arrives via ngrok or a real
    # domain (421 Invalid Host header) before it ever reaches our own auth.
    # Disabling it is safe here specifically because BearerAuthMiddleware
    # (mcp_server/auth.py) already requires a verified token on every request —
    # a DNS-rebinding attack from a victim's browser still has no token, so the
    # Host-header check buys nothing this app doesn't already enforce itself.
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    # Stateless: nothing here relies on server-held session memory — the
    # calling model tracks mandate ids itself across turns, in its own
    # conversation (see module docstring). A stateful in-memory session table
    # only creates a failure mode: any server restart (a redeploy, a crash)
    # silently orphans every connector's existing session, surfacing as a 404
    # "Invalid or expired session ID" on their very next tool call. Remote
    # connector infra (observed: rotating source IPs per request) isn't
    # holding one sticky connection anyway, so stateful buys nothing here.
    stateless_http=True,
    instructions=(
        "Guide the customer through: propose_intent -> confirm_intent -> "
        "search_catalog/propose_cart -> confirm_cart -> create_payment_link -> "
        "check_payment_status. At every step, tell the customer plainly what "
        "they can do next — never leave them guessing. Always get explicit, "
        "unambiguous human confirmation before confirm_intent and confirm_cart "
        "— a vague or non-committal reply is not consent; ask again rather "
        "than guessing. A draft intent or cart is never locked — propose_intent "
        "and propose_cart stay available right up until confirmation, so if "
        "the customer adds detail or wants another item before confirming, just "
        "redraft (cheap and safe: nothing is signed until confirm_intent/"
        "confirm_cart) — never tell them a draft can't be changed. Build "
        "search_catalog queries from the product itself, never the customer's "
        "literal sentence. search_catalog spans every merchant; when the same "
        "or a similar product appears from more than one, point that out and "
        "recommend the cheapest unless the customer prefers a specific "
        "merchant. Before confirming the cart, consider suggest_upsell once — "
        "at most one relevant add-on, zero pressure if declined, never raised "
        "again once the cart is confirmed. Whenever the customer asks about "
        "payment status or claims it succeeded/failed, ALWAYS call "
        "check_payment_status first and report exactly what it returns — it "
        "is available throughout payment, never claim otherwise, and never "
        "agree with the customer's own unverified claim. Only call "
        "retry_payment/cancel_payment when the tool's own status is 'failed'. "
        "If a payment fails, say so plainly and offer retry_payment or "
        "cancel_payment — never go silent."
    ),
)


logger = logging.getLogger("mcp_server")


@contextmanager
def _db():
    """The MCP SDK's call_tool handler swallows every tool exception into a
    generic client-facing message with zero server-side logging (mcp/server/
    lowlevel/server.py: `except Exception as e: return
    self._make_error_result(str(e))`) — without this, a real bug here is
    completely undiagnosable. Every tool routes through this context manager,
    so logging here covers the whole surface with one change."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        logger.exception("MCP tool call failed")
        raise
    finally:
        db.close()


@mcp.tool()
def propose_intent(
    ctx: Context,
    product_query: str,
    quantity: int = 1,
    budget_paise: int | None = None,
    constraints: list[str] | None = None,
) -> dict:
    """Draft a structured purchase intent. Must be confirmed by the human (confirm_intent) before searching the catalog."""
    customer_id = ctx.request_context.request.state.customer_id
    with _db() as db:
        structured = IntentExtraction(
            product_query=product_query,
            quantity=quantity,
            budget_paise=budget_paise,
            constraints=constraints or [],
        )
        mandate = create_draft_intent_from_structured(db, uuid.UUID(customer_id), product_query, structured)
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
    import uvicorn

    from mcp_server.auth import BearerAuthMiddleware

    # Not mcp.run(transport="streamable-http") — that gives no hook to add our
    # own bearer-auth middleware. Build the same ASGI app it would have built,
    # wrap it, and run uvicorn ourselves instead.
    app = BearerAuthMiddleware(mcp.streamable_http_app())
    uvicorn.run(app, host=mcp.settings.host, port=mcp.settings.port)
