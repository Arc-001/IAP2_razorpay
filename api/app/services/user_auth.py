from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import Customer, Merchant, User
from app.services.password import hash_password, verify_password


def register_user(
    db: Session, email: str, password: str, role: str, name: str, merchant_name: str | None = None
) -> User:
    """Creates the domain row (Customer/Merchant) and the User row in one
    transaction. Admin accounts are never created through this path — the
    router only accepts role in {"customer", "merchant"}; this function
    trusts its caller on that, since it's also used by the seed script to
    create the one admin account directly."""
    if db.query(User).filter(User.email == email).first() is not None:
        raise ValueError(f"an account with email '{email}' already exists")

    customer_id = None
    merchant_id = None
    if role == "customer":
        customer = Customer(name=name)
        db.add(customer)
        db.flush()
        customer_id = customer.id
    elif role == "merchant":
        if not merchant_name:
            raise ValueError("merchant_name is required when registering a merchant account")
        merchant = Merchant(name=merchant_name)
        db.add(merchant)
        db.flush()
        merchant_id = merchant.id
    elif role != "admin":
        raise ValueError(f"unknown role '{role}'")

    user = User(
        email=email,
        password_hash=hash_password(password),
        role=role,
        customer_id=customer_id,
        merchant_id=merchant_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if user is None or not verify_password(password, user.password_hash):
        raise ValueError("invalid email or password")

    user.last_login_at = datetime.now(UTC)
    db.commit()
    db.refresh(user)
    return user
