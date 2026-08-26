from datetime import UTC, datetime, timedelta

import pytest

from app.config import settings
from app.models import AuditLog, Customer, IntentMandate
from app.services.intent_mandate import confirm_intent
from app.services.mandate_expiry import is_expired


def test_is_expired_false_for_fresh_timestamp():
    assert is_expired(datetime.now(UTC)) is False


def test_is_expired_true_past_ttl():
    stale = datetime.now(UTC) - timedelta(minutes=settings.intent_expiry_minutes + 1)
    assert is_expired(stale) is True


def _make_stale_draft_intent(db_session) -> IntentMandate:
    customer = Customer(name="t")
    db_session.add(customer)
    db_session.flush()
    intent = IntentMandate(
        customer_id=customer.id,
        raw_text="x",
        structured_json={"budget_paise": None},
        status="draft",
        created_at=datetime.now(UTC) - timedelta(minutes=settings.intent_expiry_minutes + 1),
    )
    db_session.add(intent)
    db_session.commit()
    return intent


def test_confirm_expired_intent_is_rejected_and_marked_expired(db_session):
    intent = _make_stale_draft_intent(db_session)

    with pytest.raises(ValueError, match="expired"):
        confirm_intent(db_session, intent.id)

    db_session.refresh(intent)
    assert intent.status == "expired"


def test_confirm_expired_intent_writes_audit_row(db_session):
    intent = _make_stale_draft_intent(db_session)
    with pytest.raises(ValueError):
        confirm_intent(db_session, intent.id)

    row = (
        db_session.query(AuditLog)
        .filter(AuditLog.mandate_id == intent.id, AuditLog.to_state == "expired")
        .one()
    )
    assert row.from_state == "draft"


def test_confirm_fresh_intent_still_succeeds(db_session):
    customer = Customer(name="t")
    db_session.add(customer)
    db_session.flush()
    intent = IntentMandate(
        customer_id=customer.id, raw_text="x", structured_json={"budget_paise": None}, status="draft"
    )
    db_session.add(intent)
    db_session.commit()

    result = confirm_intent(db_session, intent.id)

    assert result.status == "confirmed"
