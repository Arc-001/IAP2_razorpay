import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.config import settings
from app.models import CartMandate, Customer, IntentMandate
from app.repositories.catalog import SqlAlchemyCatalogRepository
from app.schemas.cart import CartDraftRequest
from app.services.audit import record_transition
from app.services.mandate_signing import hash_payload, sign_mandate
from app.services.price_history import price_has_risen_significantly

# Flat shipping fee — the spec doesn't define a shipping-cost model, and a
# real rate table is out of scope for the demo catalog.
SHIPPING_FEE_PAISE = 4900


def _resolve_shipping_address(db: Session, customer: Customer, provided: dict | None) -> dict:
    """CLAUDE.md §11 P1.4: reuse the saved address automatically, or require
    one to be provided (the caller/agent is responsible for prompting the
    human) — collected before the cart total is shown, never after."""
    if provided is not None:
        customer.saved_address = provided
        db.flush()
        return provided
    if customer.saved_address:
        return customer.saved_address
    raise ValueError("no saved address on file — shipping_address is required")


def create_draft_cart(db: Session, request: CartDraftRequest) -> CartMandate:
    intent = db.get(IntentMandate, request.intent_mandate_id)
    if intent is None:
        raise LookupError(f"intent mandate {request.intent_mandate_id} not found")
    if intent.status != "confirmed":
        raise ValueError(
            f"intent mandate must be confirmed before building a cart (status: '{intent.status}')"
        )

    customer = db.get(Customer, intent.customer_id)
    shipping_address = _resolve_shipping_address(db, customer, request.shipping_address)

    repo = SqlAlchemyCatalogRepository(db)
    line_items = []
    subtotal = 0
    for item in request.items:
        product = repo.get_product(item.product_id)
        if product is None:
            raise LookupError(f"product {item.product_id} not found")

        risen, previous_price, current_price = price_has_risen_significantly(db, product.id)
        if risen and not request.acknowledge_price_change:
            raise ValueError(
                f"price for '{product.name}' has risen from {previous_price} to {current_price} paise "
                f"(>{int(settings.price_rise_threshold * 100)}%) since it was last known — resend with "
                f"acknowledge_price_change=true to proceed at the new price"
            )

        line_total = product.price * item.quantity
        subtotal += line_total
        line_items.append(
            {
                "product_id": str(product.id),
                "name": product.name,
                "unit_price": product.price,
                "quantity": item.quantity,
                "line_total": line_total,
            }
        )

    total_amount = subtotal + SHIPPING_FEE_PAISE

    cart = CartMandate(
        intent_mandate_id=intent.id,
        items=line_items,
        total_amount=total_amount,
        shipping_address=shipping_address,
        status="draft",
    )
    db.add(cart)
    db.flush()

    payload_hash = hash_payload(
        {"items": line_items, "total_amount": total_amount, "shipping_address": shipping_address}
    )
    record_transition(db, "cart", cart.id, None, "draft", "customer", payload_hash)
    db.commit()
    db.refresh(cart)
    return cart


def get_cart_mandate(db: Session, mandate_id: uuid.UUID) -> CartMandate | None:
    return db.get(CartMandate, mandate_id)


def confirm_cart(db: Session, mandate_id: uuid.UUID) -> CartMandate:
    cart = db.get(CartMandate, mandate_id)
    if cart is None:
        raise LookupError(f"cart mandate {mandate_id} not found")
    if cart.status != "draft":
        raise ValueError(f"cannot confirm cart mandate in status '{cart.status}'")

    intent = db.get(IntentMandate, cart.intent_mandate_id)
    budget_paise = (intent.structured_json or {}).get("budget_paise")
    if budget_paise is not None and cart.total_amount > budget_paise:
        raise ValueError(
            f"cart total {cart.total_amount} paise exceeds intent budget {budget_paise} paise"
        )

    payload_hash = hash_payload(
        {
            "items": cart.items,
            "total_amount": cart.total_amount,
            "shipping_address": cart.shipping_address,
            "intent_mandate_id": str(cart.intent_mandate_id),
        }
    )
    cart.signature = sign_mandate("cart", cart.id, payload_hash)
    cart.status = "confirmed"
    cart.confirmed_at = datetime.now(UTC)

    record_transition(db, "cart", cart.id, "draft", "confirmed", "customer", payload_hash)
    db.commit()
    db.refresh(cart)
    return cart
