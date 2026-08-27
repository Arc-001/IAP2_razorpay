"""
Seed one login-capable account per role (CLAUDE.md §13 / SCRUM-39), linked to
existing demo data rather than orphaning it: the admin has no domain row, the
merchant is linked to the first seeded Merchant (run scripts/seed_catalog.py
first), and the customer is linked to the existing lazily-created "Demo
Customer" row (same lookup as services/intent_mandate.py's _default_customer)
so pre-existing intent/cart/payment mandates stay reachable through login.

Idempotent: re-running updates the password on existing accounts rather than
erroring or duplicating them.

Run:
    uv run python scripts/create_demo_users.py
"""

from app.db import SessionLocal
from app.models import Customer, Merchant, User
from app.services.password import hash_password

DEMO_ADMIN_EMAIL = "admin@demo.local"
DEMO_MERCHANT_EMAIL = "merchant@demo.local"
DEMO_CUSTOMER_EMAIL = "customer@demo.local"
DEMO_PASSWORD = "demo1234"


def _upsert_user(db, *, email: str, role: str, customer_id=None, merchant_id=None) -> User:
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(email=email, role=role, customer_id=customer_id, merchant_id=merchant_id)
        db.add(user)
    user.password_hash = hash_password(DEMO_PASSWORD)
    db.flush()
    return user


def seed():
    db = SessionLocal()
    try:
        admin = _upsert_user(db, email=DEMO_ADMIN_EMAIL, role="admin")

        merchant_row = db.query(Merchant).first()
        merchant_user = None
        if merchant_row is not None:
            merchant_user = _upsert_user(
                db, email=DEMO_MERCHANT_EMAIL, role="merchant", merchant_id=merchant_row.id
            )
        else:
            print("No Merchant rows found — run scripts/seed_catalog.py first. Skipping merchant user.")

        customer_row = db.query(Customer).first()
        if customer_row is None:
            customer_row = Customer(name="Demo Customer")
            db.add(customer_row)
            db.flush()
        customer_user = _upsert_user(
            db, email=DEMO_CUSTOMER_EMAIL, role="customer", customer_id=customer_row.id
        )

        db.commit()

        print(f"admin:    {admin.email} / {DEMO_PASSWORD}")
        if merchant_user:
            print(f"merchant: {merchant_user.email} / {DEMO_PASSWORD}  (merchant_id={merchant_row.id})")
        print(f"customer: {customer_user.email} / {DEMO_PASSWORD}  (customer_id={customer_row.id})")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
