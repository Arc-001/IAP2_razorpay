from fastapi import APIRouter

from app.schemas.intent import IntentExtractionRequest, IntentExtractionResponse
from app.services.intent_extraction import extract_intent

router = APIRouter(prefix="/api/intent", tags=["intent"])


@router.post("/extract", response_model=IntentExtractionResponse)
def extract(request: IntentExtractionRequest):
    return extract_intent(request.raw_text)
