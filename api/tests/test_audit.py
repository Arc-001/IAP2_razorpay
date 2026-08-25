import uuid

from app.models import AuditLog
from app.services.audit import record_transition


def test_record_transition_inserts_row(db_session):
    mandate_id = uuid.uuid4()

    record_transition(db_session, "intent", mandate_id, "draft", "confirmed", "customer", "deadbeef")
    db_session.commit()

    row = db_session.query(AuditLog).filter(AuditLog.mandate_id == mandate_id).one()
    assert row.mandate_type == "intent"
    assert row.from_state == "draft"
    assert row.to_state == "confirmed"
    assert row.actor == "customer"
    assert row.payload_hash == "deadbeef"


def test_record_transition_allows_null_from_state(db_session):
    mandate_id = uuid.uuid4()

    record_transition(db_session, "intent", mandate_id, None, "draft", "customer", "abc123")
    db_session.commit()

    row = db_session.query(AuditLog).filter(AuditLog.mandate_id == mandate_id).one()
    assert row.from_state is None
