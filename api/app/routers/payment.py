import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.payment import PaymentChargeRequest, PaymentChargeResponse, PaymentMandateOut
from app.services.payment_mandate import create_payment_for_cart, get_payment_mandate

router = APIRouter(prefix="/api/payment", tags=["payment"])


@router.post("", response_model=PaymentChargeResponse)
def create_payment(request: PaymentChargeRequest, db: Session = Depends(get_db)):
    try:
        payment, charge = create_payment_for_cart(db, request.cart_mandate_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    out = PaymentMandateOut.model_validate(payment)
    return PaymentChargeResponse(**out.model_dump(), client_payload=charge.client_payload)


@router.get("/{payment_id}", response_model=PaymentMandateOut)
def get_payment(payment_id: uuid.UUID, db: Session = Depends(get_db)):
    payment = get_payment_mandate(db, payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment mandate not found")
    return payment
