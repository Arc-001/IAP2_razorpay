"""Audit trail view (CLAUDE.md §11 P2.4, gated per §13/SCRUM-45). The
append-only audit_log table already *is* the audit trail (§3.2); this makes
it visible without a database client.

Access model for the per-transaction JSON endpoint is deliberately not
admin-only: the customer-facing chat sidebar (web/src/components/AuditTrail.vue)
has depended on GET /api/audit/transactions/{intent_id} since before RBAC
existed, to show the live mandate-transition trail for a customer's own
in-progress purchase — that's a real, already-shipped feature, not
incidental exposure. Locking it to admin-only would silently break it. So:
a customer may fetch only their own intent's trail; an admin may fetch any.
Listing across every transaction (no intent_id given) has no such
customer-facing use and is admin-only, as is the raw HTML debug view (which
a plain browser navigation can't authenticate anyway, since this app has no
cookie/session auth — only bearer tokens attached by the SPA's own fetch
calls)."""

import html
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.auth import get_current_user, require_role
from app.models import User
from app.schemas.audit import AuditLogOut, TransactionAuditOut
from app.services.audit import get_transaction_audit_trail, list_recent_transactions

router = APIRouter(tags=["audit"])


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>
body {{ font-family: monospace; margin: 2rem; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ccc; padding: 0.4rem 0.6rem; text-align: left; font-size: 0.85rem; }}
th {{ background: #eee; }}
a {{ color: #0645ad; }}
</style></head><body>{body}</body></html>"""


@router.get("/api/audit/transactions", response_model=list[TransactionAuditOut])
def api_list_transactions(
    limit: int = 50, db: Session = Depends(get_db), _admin: User = Depends(require_role("admin"))
):
    intents = list_recent_transactions(db, limit=limit)
    out = []
    for intent in intents:
        trail = get_transaction_audit_trail(db, intent.id)
        out.append(_to_transaction_out(trail))
    return out


@router.get("/api/audit/transactions/{intent_id}", response_model=TransactionAuditOut)
def api_get_transaction(
    intent_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    try:
        trail = get_transaction_audit_trail(db, intent_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    is_owner = current_user.role == "customer" and trail.intent.customer_id == current_user.customer_id
    if current_user.role != "admin" and not is_owner:
        # 404, not 403 — don't confirm to a non-owning customer that this
        # transaction even exists.
        raise HTTPException(status_code=404, detail=f"intent mandate {intent_id} not found")

    return _to_transaction_out(trail)


def _to_transaction_out(trail) -> TransactionAuditOut:
    return TransactionAuditOut(
        intent_id=trail.intent.id,
        intent_status=trail.intent.status,
        intent_signature=trail.intent.signature,
        cart_ids=[c.id for c in trail.carts],
        cart_signatures=[c.signature for c in trail.carts if c.signature],
        payment_ids=[p.id for p in trail.payments],
        payment_statuses=[p.status for p in trail.payments],
        payment_signature_verified=[p.signature_verified for p in trail.payments],
        entries=[AuditLogOut.model_validate(e) for e in trail.entries],
    )


@router.get("/audit", response_class=HTMLResponse)
def audit_index(limit: int = 50, db: Session = Depends(get_db), _admin: User = Depends(require_role("admin"))):
    intents = list_recent_transactions(db, limit=limit)
    rows = "\n".join(
        f"<tr><td><a href='/audit/{i.id}'>{i.id}</a></td>"
        f"<td>{html.escape(i.status)}</td>"
        f"<td>{html.escape((i.raw_text or '')[:80])}</td>"
        f"<td>{i.created_at.isoformat()}</td></tr>"
        for i in intents
    )
    body = (
        "<h2>Transactions (Intent → Cart → Payment)</h2>"
        "<table><tr><th>Intent ID</th><th>Status</th><th>Request</th><th>Created</th></tr>"
        f"{rows}</table>"
    )
    return _page("Audit trail", body)


@router.get("/audit/{intent_id}", response_class=HTMLResponse)
def audit_transaction(
    intent_id: uuid.UUID, db: Session = Depends(get_db), _admin: User = Depends(require_role("admin"))
):
    try:
        trail = get_transaction_audit_trail(db, intent_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    summary = (
        f"<p><b>Intent:</b> {trail.intent.id} ({html.escape(trail.intent.status)})<br>"
        f"<b>Cart(s):</b> {', '.join(str(c.id) for c in trail.carts) or '—'}<br>"
        f"<b>Payment(s):</b> {', '.join(str(p.id) for p in trail.payments) or '—'}</p>"
    )
    rows = "\n".join(
        f"<tr><td>{e.created_at.isoformat()}</td>"
        f"<td>{html.escape(e.mandate_type)}</td>"
        f"<td>{e.mandate_id}</td>"
        f"<td>{html.escape(e.from_state or '')}</td>"
        f"<td>{html.escape(e.to_state or '')}</td>"
        f"<td>{html.escape(e.actor or '')}</td>"
        f"<td>{html.escape((e.payload_hash or '')[:24])}</td></tr>"
        for e in trail.entries
    )
    body = (
        "<p><a href='/audit'>&larr; all transactions</a></p>"
        f"<h2>Transaction {trail.intent.id}</h2>"
        f"{summary}"
        "<table><tr><th>When</th><th>Mandate</th><th>Mandate ID</th>"
        "<th>From</th><th>To</th><th>Actor</th><th>Payload hash</th></tr>"
        f"{rows}</table>"
    )
    return _page(f"Transaction {trail.intent.id}", body)
