import pytest

from app.models import Customer
from app.orchestrator.context import MandateContext
from app.orchestrator.orchestrator import OrchestratorTurnResult
from app.orchestrator.state import AgentState
from app.services.chat_history import (
    append_turn,
    get_conversation,
    get_or_create_conversation,
    list_conversations,
)


@pytest.fixture()
def customer(db_session):
    c = Customer(name="Test Customer")
    db_session.add(c)
    db_session.flush()
    return c


def _fake_result(state=AgentState.DRAFTING_INTENT, customer_id=None, reply="ok", tool_calls=None):
    return OrchestratorTurnResult(
        state=state,
        context=MandateContext(customer_id=customer_id, intent_id=None, cart_id=None, payment_id=None),
        reply=reply,
        tool_calls=tool_calls or [],
        new_messages=[{"role": "user", "content": "hi"}, {"role": "assistant", "content": reply}],
    )


def test_get_or_create_with_no_id_creates_a_new_conversation(db_session, customer):
    conversation = get_or_create_conversation(db_session, customer.id, None)

    assert conversation.customer_id == customer.id
    assert conversation.history == []
    assert conversation.display_log == []


def test_get_or_create_with_existing_id_returns_that_conversation(db_session, customer):
    created = get_or_create_conversation(db_session, customer.id, None)
    db_session.commit()

    fetched = get_or_create_conversation(db_session, customer.id, created.id)

    assert fetched.id == created.id


def test_get_or_create_raises_for_a_conversation_belonging_to_someone_else(db_session, customer):
    other_customer = Customer(name="Other")
    db_session.add(other_customer)
    db_session.flush()

    created = get_or_create_conversation(db_session, other_customer.id, None)
    db_session.commit()

    with pytest.raises(LookupError):
        get_or_create_conversation(db_session, customer.id, created.id)


def test_append_turn_records_history_and_display_log(db_session, customer):
    conversation = get_or_create_conversation(db_session, customer.id, None)
    result = _fake_result(customer_id=customer.id, reply="Here's a draft.")

    updated = append_turn(db_session, conversation, "I want earbuds", result)

    assert updated.history == result.new_messages
    assert updated.display_log[0] == {"role": "user", "text": "I want earbuds"}
    assert updated.display_log[1]["role"] == "assistant"
    assert updated.display_log[1]["text"] == "Here's a draft."
    assert updated.state == AgentState.DRAFTING_INTENT.value
    assert updated.title == "I want earbuds"


def test_append_turn_marks_stalled_when_state_unchanged_and_no_tools_ran(db_session, customer):
    conversation = get_or_create_conversation(db_session, customer.id, None)
    conversation.state = AgentState.AWAITING_INTENT_OK.value
    db_session.flush()

    result = _fake_result(state=AgentState.AWAITING_INTENT_OK, customer_id=customer.id, tool_calls=[])
    updated = append_turn(db_session, conversation, "hmm?", result)

    assert updated.display_log[-1]["stalled"] is True


def test_append_turn_accumulates_across_multiple_turns(db_session, customer):
    conversation = get_or_create_conversation(db_session, customer.id, None)

    append_turn(db_session, conversation, "first", _fake_result(reply="a"))
    updated = append_turn(db_session, conversation, "second", _fake_result(reply="b"))

    assert len(updated.history) == 4
    assert len(updated.display_log) == 4
    assert updated.title == "first"  # only set once, on the first turn


def test_list_conversations_only_returns_the_given_customers_rows(db_session, customer):
    other_customer = Customer(name="Other")
    db_session.add(other_customer)
    db_session.flush()

    get_or_create_conversation(db_session, customer.id, None)
    get_or_create_conversation(db_session, other_customer.id, None)
    db_session.commit()

    conversations = list_conversations(db_session, customer.id)

    assert len(conversations) == 1
    assert conversations[0].customer_id == customer.id


def test_get_conversation_raises_for_unknown_id(db_session, customer):
    import uuid

    with pytest.raises(LookupError):
        get_conversation(db_session, customer.id, uuid.uuid4())
