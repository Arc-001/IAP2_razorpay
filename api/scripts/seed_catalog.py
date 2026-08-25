"""
Seed the single hardcoded merchant catalog (CLAUDE.md §10, §11 P1.1).
Idempotent: re-running clears and reloads TechBazaar's catalog only.

Run:
    uv run python scripts/seed_catalog.py
"""

import json
from pathlib import Path

from app.db import SessionLocal
from app.models import Merchant, PriceHistory, Product

SEED_PATH = Path(__file__).parent.parent / "app" / "data" / "catalog_seed.json"


def seed():
    data = json.loads(SEED_PATH.read_text())
    db = SessionLocal()
    try:
        existing = db.query(Merchant).filter(Merchant.name == data["merchant"]["name"]).first()
        if existing:
            product_ids = [p.id for p in db.query(Product).filter(Product.merchant_id == existing.id).all()]
            db.query(PriceHistory).filter(PriceHistory.product_id.in_(product_ids)).delete(synchronize_session=False)
            db.query(Product).filter(Product.merchant_id == existing.id).delete(synchronize_session=False)
            db.delete(existing)
            db.flush()

        merchant = Merchant(name=data["merchant"]["name"])
        db.add(merchant)
        db.flush()

        for p in data["products"]:
            product = Product(
                merchant_id=merchant.id,
                name=p["name"],
                description=p["description"],
                price=p["price"],
                stock=p["stock"],
            )
            db.add(product)
            db.flush()
            db.add(PriceHistory(product_id=product.id, price=product.price))

        db.commit()
        print(f"Seeded merchant '{merchant.name}' ({merchant.id}) with {len(data['products'])} products.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
