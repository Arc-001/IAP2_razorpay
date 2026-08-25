"""Append-only audit trail (CLAUDE.md §3.2) — every mandate transition is an
INSERT here, never an UPDATE to this table."""

import uuid

from sqlalchemy.orm import Session

from app.models import AuditLog


def record_transition(
    db: Session,
    mandate_type: str,
    mandate_id: uuid.UUID,
    from_state: str | None,
    to_state: str,
    actor: str,
    payload_hash: str,
) -> None:
    db.add(
        AuditLog(
            mandate_type=mandate_type,
            mandate_id=mandate_id,
            from_state=from_state,
            to_state=to_state,
            actor=actor,
            payload_hash=payload_hash,
        )
    )
