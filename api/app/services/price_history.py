import uuid

from sqlalchemy.orm import Session

from app.config import settings
from app.models import PriceHistory, Product


def record_price_change(db: Session, product_id: uuid.UUID, new_price: int) -> Product:
    """Append-only price_history insert + product.price update. There's no
    merchant catalog-push pipeline (CLAUDE.md §10), so this is also the
    live-demo trigger for the price-change re-confirmation rule."""
    product = db.get(Product, product_id)
    if product is None:
        raise LookupError(f"product {product_id} not found")
    product.price = new_price
    db.add(PriceHistory(product_id=product.id, price=new_price))
    db.commit()
    db.refresh(product)
    return product


def price_has_risen_significantly(db: Session, product_id: uuid.UUID) -> tuple[bool, int | None, int]:
    """Compare a product's current price against the one recorded immediately
    before it in price_history (CLAUDE.md §5: "reject/re-confirm if price
    has risen >10% since last known price"). Returns
    (risen_significantly, previous_price_or_none, current_price)."""
    product = db.get(Product, product_id)
    if product is None:
        raise LookupError(f"product {product_id} not found")

    history = (
        db.query(PriceHistory)
        .filter(PriceHistory.product_id == product_id)
        .order_by(PriceHistory.changed_at.desc())
        .limit(2)
        .all()
    )
    if len(history) < 2:
        return False, None, product.price

    previous_price = history[1].price
    risen = product.price > previous_price * (1 + settings.price_rise_threshold)
    return risen, previous_price, product.price
