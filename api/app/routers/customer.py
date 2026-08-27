import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.auth import require_role
from app.models import User
from app.schemas.customer import ConversationDetailOut, ConversationSummaryOut
from app.services.chat_history import get_conversation, list_conversations

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
