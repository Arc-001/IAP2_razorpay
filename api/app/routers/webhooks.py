import json

import razorpay
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.services.payment_webhook import process_payment_webhook

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/razorpay")
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    """One webhook URL is registered account-wide (CLAUDE.md §6.7) — all
    events land here and get disambiguated by `event`. Signature must verify
    against the raw body before anything in the payload is trusted."""
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")

    client = razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))
    try:
        client.utility.verify_webhook_signature(body.decode(), signature, settings.razorpay_webhook_secret)
    except razorpay.errors.SignatureVerificationError as e:
        raise HTTPException(status_code=400, detail="invalid webhook signature") from e

    payload = json.loads(body)
    event = payload.get("event", "")
    payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})

    process_payment_webhook(db, event, payment_entity)
    return {"status": "ok"}
