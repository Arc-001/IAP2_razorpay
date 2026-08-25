import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.cart import CartDraftRequest, CartMandateOut
from app.services.cart_mandate import confirm_cart, create_draft_cart, get_cart_mandate

router = APIRouter(prefix="/api/cart", tags=["cart"])


@router.post("", response_model=CartMandateOut)
def draft(request: CartDraftRequest, db: Session = Depends(get_db)):
    try:
        return create_draft_cart(db, request)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{mandate_id}", response_model=CartMandateOut)
def get_cart(mandate_id: uuid.UUID, db: Session = Depends(get_db)):
    cart = get_cart_mandate(db, mandate_id)
    if cart is None:
        raise HTTPException(status_code=404, detail="Cart mandate not found")
    return cart


@router.post("/{mandate_id}/confirm", response_model=CartMandateOut)
def confirm(mandate_id: uuid.UUID, db: Session = Depends(get_db)):
    if get_cart_mandate(db, mandate_id) is None:
        raise HTTPException(status_code=404, detail="Cart mandate not found")
    try:
        return confirm_cart(db, mandate_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
