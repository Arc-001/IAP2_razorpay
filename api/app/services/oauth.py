"""OAuth 2.1 + PKCE service logic for the MCP server's connector flow (see
plan "Add real OAuth to the MCP server"). Pure logic only — no HTTP here,
that's app/routers/oauth.py.

Two kinds of ephemeral, in-memory state (never persisted — see
app/models/oauth.py's docstring for why): pending /oauth/authorize requests
(between the redirect-in and the customer's login/consent) and pending
grants/authorization codes (between consent and the token exchange). Both
live seconds, not days — losing either on a restart just means the customer
retries the connect. Refresh tokens are the one thing here that DOES need to
survive a restart, so those alone are persisted (OAuthRefreshToken), hashed
at rest like passwords.
"""

import base64
import hashlib
import secrets
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.models import OAuthRefreshToken


def verify_pkce(code_verifier: str, code_challenge: str) -> bool:
    """RFC 7636 S256: code_challenge must equal base64url(sha256(code_verifier)),
    unpadded. Constant-time compare — this is a security check, not a lookup."""
    digest = hashlib.sha256(code_verifier.encode()).digest()
    computed = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return secrets.compare_digest(computed, code_challenge)


@dataclass
class PendingAuthRequest:
    client_id: str
    redirect_uri: str
    state: str
    code_challenge: str
    expires_at: datetime


@dataclass
class PendingGrant:
    user_id: uuid.UUID
    client_id: str
    redirect_uri: str
    code_challenge: str
    expires_at: datetime


_lock = threading.Lock()
_pending_requests: dict[str, PendingAuthRequest] = {}
_pending_grants: dict[str, PendingGrant] = {}


def _ttl() -> timedelta:
    return timedelta(seconds=settings.oauth_authorization_code_ttl_seconds)


def create_pending_request(*, client_id: str, redirect_uri: str, state: str, code_challenge: str) -> str:
    """Called by GET /oauth/authorize once client_id/redirect_uri pass the
    allowlist check. Returns a request_id for the consent page to reference —
    the frontend never sees or re-validates the raw client_id/redirect_uri."""
    request_id = secrets.token_urlsafe(32)
    with _lock:
        _pending_requests[request_id] = PendingAuthRequest(
            client_id=client_id,
            redirect_uri=redirect_uri,
            state=state,
            code_challenge=code_challenge,
            expires_at=datetime.now(UTC) + _ttl(),
        )
    return request_id


def consume_pending_request(request_id: str) -> PendingAuthRequest | None:
    """Single-use: pops the entry regardless of outcome, so a request_id never
    grants two authorization codes. None if unknown or expired."""
    with _lock:
        pending = _pending_requests.pop(request_id, None)
    if pending is None or pending.expires_at < datetime.now(UTC):
        return None
    return pending


def issue_authorization_code(*, user_id: uuid.UUID, client_id: str, redirect_uri: str, code_challenge: str) -> str:
    """Called by POST /oauth/authorize/{request_id}/approve after the customer
    consents. user_id is the Users table id (not the Customer FK) — it's what
    POST /oauth/token needs to mint an access token via create_access_token,
    the same way routers/auth.py's login/register already do. The code
    carries this *approved* identity forward to the token exchange — POST
    /oauth/token never has to trust the caller about who they are, only
    prove they hold this code + its PKCE verifier."""
    code = secrets.token_urlsafe(32)
    with _lock:
        _pending_grants[code] = PendingGrant(
            user_id=user_id,
            client_id=client_id,
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            expires_at=datetime.now(UTC) + _ttl(),
        )
    return code


def consume_authorization_code(code: str) -> PendingGrant | None:
    """Single-use: pops regardless of outcome, so a replayed code always
    fails on its second use, not just an expired one."""
    with _lock:
        grant = _pending_grants.pop(code, None)
    if grant is None or grant.expires_at < datetime.now(UTC):
        return None
    return grant


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def issue_refresh_token(db: Session, *, user_id: uuid.UUID, client_id: str) -> str:
    """Mints a fresh refresh token for the initial authorization_code grant.
    Only its hash is ever persisted — same discipline services/password.py
    already applies to passwords."""
    raw = secrets.token_urlsafe(48)
    db.add(OAuthRefreshToken(token_hash=_hash_token(raw), user_id=user_id, client_id=client_id))
    db.commit()
    return raw


def rotate_refresh_token(db: Session, *, raw_token: str, client_id: str) -> tuple[uuid.UUID, str] | None:
    """Verifies raw_token, then atomically revokes it and issues a
    replacement in one commit — a stolen-and-later-replayed old refresh
    token is detectably invalid (its hash no longer matches an active row),
    since using it once immediately revokes it here. Returns (user_id,
    new_raw_token), or None if the token is unknown, already revoked,
    expired, or was issued to a different client."""
    row = db.query(OAuthRefreshToken).filter(OAuthRefreshToken.token_hash == _hash_token(raw_token)).first()
    if row is None or row.revoked_at is not None or row.client_id != client_id:
        return None
    if row.created_at < datetime.now(UTC) - timedelta(days=settings.oauth_refresh_token_ttl_days):
        return None

    row.revoked_at = datetime.now(UTC)
    new_raw = secrets.token_urlsafe(48)
    db.add(OAuthRefreshToken(token_hash=_hash_token(new_raw), user_id=row.user_id, client_id=client_id))
    db.commit()
    return row.user_id, new_raw
