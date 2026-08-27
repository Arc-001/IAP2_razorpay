from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.auth import require_role
from app.models import User
from app.orchestrator.context import MandateContext
from app.orchestrator.orchestrator import run_turn
from app.schemas.orchestrator import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("customer")),
):
    # customer_id is never taken from the request body — before this, any
    # caller could claim to be any customer by simply naming their id.
    context = MandateContext(
        customer_id=current_user.customer_id,
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
