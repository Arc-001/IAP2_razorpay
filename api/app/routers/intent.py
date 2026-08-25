import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.intent import (
    IntentDraftRequest,
    IntentExtractionRequest,
    IntentExtractionResponse,
    IntentMandateOut,
)
from app.services.intent_extraction import extract_intent
from app.services.intent_mandate import confirm_intent, create_draft_intent, get_intent_mandate

router = APIRouter(prefix="/api/intent", tags=["intent"])


@router.post("/extract", response_model=IntentExtractionResponse)
def extract(request: IntentExtractionRequest):
    """Preview-only extraction, no persistence — useful for inspecting what
    the model would propose before committing to a draft mandate."""
    return extract_intent(request.raw_text)


@router.post("", response_model=IntentMandateOut)
def draft(request: IntentDraftRequest, db: Session = Depends(get_db)):
    try:
        return create_draft_intent(db, request.raw_text, request.customer_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/{mandate_id}", response_model=IntentMandateOut)
def get_intent(mandate_id: uuid.UUID, db: Session = Depends(get_db)):
    mandate = get_intent_mandate(db, mandate_id)
    if mandate is None:
        raise HTTPException(status_code=404, detail="Intent mandate not found")
    return mandate


@router.post("/{mandate_id}/confirm", response_model=IntentMandateOut)
def confirm(mandate_id: uuid.UUID, db: Session = Depends(get_db)):
    try:
        return confirm_intent(db, mandate_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
