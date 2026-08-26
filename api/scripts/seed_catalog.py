"""
Seed the hardcoded merchant catalogs (CLAUDE.md §10, §11 P1.1/P3.3) — plain
JSON files, no merchant onboarding/push pipeline. Idempotent per merchant:
re-running clears and reloads each seed file's own merchant only, leaving
the others untouched.

Run:
    uv run python scripts/seed_catalog.py
"""

import json
from pathlib import Path

from app.db import SessionLocal
from app.models import Merchant, PriceHistory, Product

DATA_DIR = Path(__file__).parent.parent / "app" / "data"
SEED_FILES = [
    DATA_DIR / "catalog_seed.json",  # TechBazaar
    DATA_DIR / "catalog_seed_gadgetgalaxy.json",
    DATA_DIR / "catalog_seed_mobikart.json",
]


def _seed_one(db, seed_path: Path):
    data = json.loads(seed_path.read_text())

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


def seed():
    db = SessionLocal()
    try:
        for seed_path in SEED_FILES:
            _seed_one(db, seed_path)
    finally:
        db.close()


if __name__ == "__main__":
    seed()
