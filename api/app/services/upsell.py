"""Upsell suggestion (CLAUDE.md §11 P3.1, design pattern §3.4 non-goal: no
trained recommender). This service only does the boring half — finding
same-merchant candidates the customer hasn't already picked. The actual
"suggesting" (picking the single best one, phrasing it to the customer) is
the orchestrating LLM's job when it relays this tool's output — that's what
"LLM-prompted using the catalog as context" means in practice: no second
model call, no training data, just the existing loop given more context."""

import uuid

from sqlalchemy.orm import Session

from app.models import Product


def suggest_upsell_candidates(
    db: Session, selected_product_ids: list[uuid.UUID], limit: int = 5
) -> list[Product]:
    if not selected_product_ids:
        return []

    selected = db.query(Product).filter(Product.id.in_(selected_product_ids)).all()
    if not selected:
        return []

    merchant_ids = {p.merchant_id for p in selected}
    return (
        db.query(Product)
        .filter(Product.merchant_id.in_(merchant_ids), Product.id.notin_(selected_product_ids))
        .order_by(Product.name)
        .limit(limit)
        .all()
    )
