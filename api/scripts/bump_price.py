"""Live-demo trigger for the price-change re-confirmation rule (CLAUDE.md
§11 P2.3): bump a product's price and record it in price_history, the same
way a merchant catalog update would in a real system.

Run:
    uv run python scripts/bump_price.py <product_id> <new_price_paise>
"""

import sys
import uuid

from app.db import SessionLocal
from app.services.price_history import record_price_change

if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: bump_price.py <product_id> <new_price_paise>")

    db = SessionLocal()
    try:
        product = record_price_change(db, uuid.UUID(sys.argv[1]), int(sys.argv[2]))
        print(f"{product.name}: now {product.price} paise")
    finally:
        db.close()
