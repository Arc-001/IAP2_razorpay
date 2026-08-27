import uuid

from sqlalchemy.orm import Session

from app.models import CustomerAddress


def address_to_dict(address: CustomerAddress) -> dict:
    """Shapes an address row into the same free-form dict already used for
    cart_mandates.shipping_address — no fixed schema there (CLAUDE.md), so
    this is a plain field dump, not a DTO."""
    return {
        "label": address.label,
        "line1": address.line1,
        "line2": address.line2,
        "city": address.city,
        "state": address.state,
        "postal_code": address.postal_code,
        "country": address.country,
    }


def list_addresses(db: Session, customer_id: uuid.UUID) -> list[CustomerAddress]:
    return (
        db.query(CustomerAddress)
        .filter(CustomerAddress.customer_id == customer_id)
        .order_by(CustomerAddress.is_default.desc(), CustomerAddress.created_at.desc())
        .all()
    )


def get_default_address(db: Session, customer_id: uuid.UUID) -> CustomerAddress | None:
    return (
        db.query(CustomerAddress)
        .filter(CustomerAddress.customer_id == customer_id, CustomerAddress.is_default.is_(True))
        .first()
    )


def _get_owned(db: Session, customer_id: uuid.UUID, address_id: uuid.UUID) -> CustomerAddress:
    address = (
        db.query(CustomerAddress)
        .filter(CustomerAddress.id == address_id, CustomerAddress.customer_id == customer_id)
        .first()
    )
    if address is None:
        raise LookupError(f"address {address_id} not found")
    return address


def create_address(
    db: Session,
    customer_id: uuid.UUID,
    *,
    label: str | None = None,
    line1: str,
    line2: str | None = None,
    city: str | None = None,
    state: str | None = None,
    postal_code: str | None = None,
    country: str = "IN",
    is_default: bool = False,
) -> CustomerAddress:
    # The first address a customer ever adds becomes the default automatically
    # — otherwise a brand-new account with exactly one address on file would
    # have no default and _resolve_shipping_address would fall through to
    # asking for one again.
    make_default = is_default or not list_addresses(db, customer_id)
    if make_default:
        db.query(CustomerAddress).filter(CustomerAddress.customer_id == customer_id).update({"is_default": False})

    address = CustomerAddress(
        customer_id=customer_id,
        label=label,
        line1=line1,
        line2=line2,
        city=city,
        state=state,
        postal_code=postal_code,
        country=country,
        is_default=make_default,
    )
    db.add(address)
    db.commit()
    db.refresh(address)
    return address


def update_address(db: Session, customer_id: uuid.UUID, address_id: uuid.UUID, **fields) -> CustomerAddress:
    address = _get_owned(db, customer_id, address_id)

    make_default = fields.pop("is_default", None)
    for key, value in fields.items():
        setattr(address, key, value)

    if make_default:
        db.query(CustomerAddress).filter(
            CustomerAddress.customer_id == customer_id, CustomerAddress.id != address.id
        ).update({"is_default": False})
        address.is_default = True

    db.commit()
    db.refresh(address)
    return address


def delete_address(db: Session, customer_id: uuid.UUID, address_id: uuid.UUID) -> None:
    address = _get_owned(db, customer_id, address_id)
    was_default = address.is_default
    db.delete(address)
    db.flush()

    if was_default:
        remaining = list_addresses(db, customer_id)
        if remaining:
            remaining[0].is_default = True

    db.commit()
