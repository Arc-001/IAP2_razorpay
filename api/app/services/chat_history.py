import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import Conversation
from app.orchestrator.orchestrator import OrchestratorTurnResult


def get_or_create_conversation(
    db: Session, customer_id: uuid.UUID, conversation_id: uuid.UUID | None
) -> Conversation:
    if conversation_id is not None:
        conversation = (
            db.query(Conversation)
            .filter(Conversation.id == conversation_id, Conversation.customer_id == customer_id)
            .first()
        )
        if conversation is None:
            raise LookupError(f"conversation {conversation_id} not found")
        return conversation

    conversation = Conversation(customer_id=customer_id, history=[], display_log=[])
    db.add(conversation)
    db.flush()
    return conversation


def append_turn(db: Session, conversation: Conversation, user_message: str, result: OrchestratorTurnResult) -> Conversation:
    """Mirrors exactly what the frontend's own conversation.ts store builds
    for its local displayLog (web/src/stores/conversation.ts) — the two
    representations must stay interchangeable so a resumed conversation
    renders identically to one that was live the whole time."""
    stalled = len(result.tool_calls) == 0 and conversation.state == result.state.value

    if conversation.title is None:
        conversation.title = user_message[:80]

    # Reassign (don't mutate in place) — SQLAlchemy only detects JSONB
    # column changes on a new object, not on .append() to the existing list.
    conversation.history = [*conversation.history, *result.new_messages]
    conversation.display_log = [
        *conversation.display_log,
        {"role": "user", "text": user_message},
        {"role": "assistant", "text": result.reply, "toolCalls": result.tool_calls, "stalled": stalled},
    ]
    conversation.intent_id = result.context.intent_id
    conversation.cart_id = result.context.cart_id
    conversation.payment_id = result.context.payment_id
    conversation.state = result.state.value
    conversation.updated_at = datetime.now(UTC)

    db.commit()
    db.refresh(conversation)
    return conversation


def list_conversations(db: Session, customer_id: uuid.UUID) -> list[Conversation]:
    return (
        db.query(Conversation)
        .filter(Conversation.customer_id == customer_id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )


def get_conversation(db: Session, customer_id: uuid.UUID, conversation_id: uuid.UUID) -> Conversation:
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.customer_id == customer_id)
        .first()
    )
    if conversation is None:
        raise LookupError(f"conversation {conversation_id} not found")
    return conversation
