import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.auth import require_role
from app.models import Customer, User
from app.schemas.customer import (
    AddressIn,
    AddressOut,
    AddressUpdate,
    ConversationDetailOut,
    ConversationSummaryOut,
    OrderSummaryOut,
    ProfileOut,
    ProfileUpdate,
)
from app.services.chat_history import get_conversation, list_conversations
from app.services.customer_addresses import (
    create_address,
    delete_address,
    list_addresses,
    update_address,
)
from app.services.orders import list_customer_orders

router = APIRouter(prefix="/api/me", tags=["customer"])


@router.get("/conversations", response_model=list[ConversationSummaryOut])
def get_my_conversations(db: Session = Depends(get_db), current_user: User = Depends(require_role("customer"))):
    return list_conversations(db, current_user.customer_id)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailOut)
def get_my_conversation(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("customer")),
):
    try:
        return get_conversation(db, current_user.customer_id, conversation_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/profile", response_model=ProfileOut)
def get_my_profile(db: Session = Depends(get_db), current_user: User = Depends(require_role("customer"))):
    return db.get(Customer, current_user.customer_id)


@router.patch("/profile", response_model=ProfileOut)
def update_my_profile(
    request: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("customer")),
):
    customer = db.get(Customer, current_user.customer_id)
    for key, value in request.model_dump(exclude_unset=True).items():
        setattr(customer, key, value)
    db.commit()
    db.refresh(customer)
    return customer


@router.get("/addresses", response_model=list[AddressOut])
def get_my_addresses(db: Session = Depends(get_db), current_user: User = Depends(require_role("customer"))):
    return list_addresses(db, current_user.customer_id)


@router.post("/addresses", response_model=AddressOut)
def add_my_address(
    request: AddressIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("customer")),
):
    return create_address(db, current_user.customer_id, **request.model_dump())


@router.patch("/addresses/{address_id}", response_model=AddressOut)
def edit_my_address(
    address_id: uuid.UUID,
    request: AddressUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("customer")),
):
    try:
        return update_address(db, current_user.customer_id, address_id, **request.model_dump(exclude_unset=True))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.delete("/addresses/{address_id}", status_code=204)
def remove_my_address(
    address_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("customer")),
):
    try:
        delete_address(db, current_user.customer_id, address_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/orders", response_model=list[OrderSummaryOut])
def get_my_orders(db: Session = Depends(get_db), current_user: User = Depends(require_role("customer"))):
    summaries = list_customer_orders(db, current_user.customer_id)
    return [
        OrderSummaryOut(
            intent_id=s.intent.id,
            created_at=s.intent.created_at,
            intent_status=s.intent.status,
            product_query=(s.intent.structured_json or {}).get("product_query"),
            cart_id=s.cart.id if s.cart else None,
            cart_status=s.cart.status if s.cart else None,
            total_amount=s.cart.total_amount if s.cart else None,
            payment_id=s.payment.id if s.payment else None,
            payment_status=s.payment.status if s.payment else None,
            razorpay_payment_id=s.payment.razorpay_payment_id if s.payment else None,
        )
        for s in summaries
    ]
