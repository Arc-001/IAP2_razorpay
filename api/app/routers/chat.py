from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.orchestrator.context import MandateContext
from app.orchestrator.orchestrator import run_turn
from app.schemas.orchestrator import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    context = MandateContext(
        customer_id=request.customer_id,
        intent_id=request.intent_id,
        cart_id=request.cart_id,
        payment_id=request.payment_id,
    )
    try:
        result = run_turn(db, context, request.message, request.history)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    return ChatResponse(
        state=result.state.value,
        reply=result.reply,
        customer_id=result.context.customer_id,
        intent_id=result.context.intent_id,
        cart_id=result.context.cart_id,
        payment_id=result.context.payment_id,
        tool_calls=result.tool_calls,
        new_messages=result.new_messages,
    )
