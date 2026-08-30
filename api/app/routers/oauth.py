"""OAuth 2.1 + PKCE endpoints for the MCP server's connector flow (see plan
"Add real OAuth to the MCP server"). Discovery metadata for the *backend* as
an Authorization Server lives here too — the *resource* metadata
(oauth-protected-resource) lives on the MCP server itself instead, since
that's what RFC 9728 describes (see mcp_server/auth.py).

Exactly one pre-registered client (settings.oauth_client_id /
oauth_redirect_uris) — no Dynamic Client Registration, no CIMD. See the
plan's §1 for why that's a deliberate scope line, not a shortcut taken
without noticing the alternative.
"""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.dependencies.auth import require_role
from app.models import User
from app.schemas.oauth import ApproveResponse, TokenGrantResponse
from app.services.auth_tokens import create_access_token
from app.services.oauth import (
    consume_authorization_code,
    consume_pending_request,
    create_pending_request,
    issue_authorization_code,
    issue_refresh_token,
    rotate_refresh_token,
    verify_pkce,
)

router = APIRouter(tags=["oauth"])


def _append_query(url: str, params: dict[str, str]) -> str:
    """Adds params to url's query string, preserving whatever's already
    there — redirect_uri isn't guaranteed to be bare."""
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    query.update(params)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _frontend_origin() -> str:
    # cors_origins already tracks exactly this — the browser-facing SPA's
    # origin — so this reuses it instead of introducing a second setting
    # that would need to be kept in sync with it.
    return settings.cors_origins[0]


@router.get("/.well-known/oauth-authorization-server")
def authorization_server_metadata(request: Request):
    issuer = str(request.base_url).rstrip("/")
    return {
        "issuer": issuer,
        "authorization_endpoint": f"{issuer}/oauth/authorize",
        "token_endpoint": f"{issuer}/oauth/token",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
    }


@router.get("/oauth/authorize")
def authorize(
    response_type: str,
    client_id: str,
    redirect_uri: str,
    state: str,
    code_challenge: str,
    code_challenge_method: str = "S256",
    scope: str | None = None,
):
    if response_type != "code":
        return HTMLResponse("<h1>Invalid OAuth request</h1><p>response_type must be 'code'.</p>", status_code=400)
    if code_challenge_method != "S256":
        return HTMLResponse(
            "<h1>Invalid OAuth request</h1><p>code_challenge_method must be 'S256'.</p>", status_code=400
        )
    if client_id != settings.oauth_client_id:
        return HTMLResponse("<h1>Invalid OAuth request</h1><p>Unknown client_id.</p>", status_code=400)
    if redirect_uri not in settings.oauth_redirect_uris:
        # Exact match only — never a prefix match (plan §9: a common
        # real-world redirect_uri validation bug). Never redirect the
        # browser to an unvalidated redirect_uri, even to report this error.
        return HTMLResponse("<h1>Invalid OAuth request</h1><p>Unknown redirect_uri.</p>", status_code=400)

    request_id = create_pending_request(
        client_id=client_id, redirect_uri=redirect_uri, state=state, code_challenge=code_challenge
    )
    return RedirectResponse(f"{_frontend_origin()}/oauth/consent?request_id={request_id}", status_code=302)


@router.post("/oauth/authorize/{request_id}/approve", response_model=ApproveResponse)
def approve(request_id: str, current_user: User = Depends(require_role("customer")), db: Session = Depends(get_db)):
    pending = consume_pending_request(request_id)
    if pending is None:
        raise HTTPException(status_code=404, detail="authorization request not found or expired")

    code = issue_authorization_code(
        user_id=current_user.id,
        client_id=pending.client_id,
        redirect_uri=pending.redirect_uri,
        code_challenge=pending.code_challenge,
    )
    redirect_to = _append_query(pending.redirect_uri, {"code": code, "state": pending.state})
    return ApproveResponse(redirect_to=redirect_to)


@router.post("/oauth/token", response_model=TokenGrantResponse)
def token(
    grant_type: str = Form(...),
    code: str | None = Form(None),
    redirect_uri: str | None = Form(None),
    client_id: str | None = Form(None),
    code_verifier: str | None = Form(None),
    refresh_token: str | None = Form(None),
    db: Session = Depends(get_db),
):
    if grant_type == "authorization_code":
        return _exchange_authorization_code(db, code, redirect_uri, client_id, code_verifier)
    if grant_type == "refresh_token":
        return _exchange_refresh_token(db, refresh_token, client_id)
    raise HTTPException(status_code=400, detail="unsupported_grant_type")


def _exchange_authorization_code(
    db: Session, code: str | None, redirect_uri: str | None, client_id: str | None, code_verifier: str | None
) -> TokenGrantResponse:
    if not code or not redirect_uri or not client_id or not code_verifier:
        raise HTTPException(status_code=400, detail="invalid_request")

    grant = consume_authorization_code(code)
    if grant is None:
        raise HTTPException(status_code=400, detail="invalid_grant")
    if grant.client_id != client_id or grant.redirect_uri != redirect_uri:
        raise HTTPException(status_code=400, detail="invalid_grant")
    if not verify_pkce(code_verifier, grant.code_challenge):
        raise HTTPException(status_code=400, detail="invalid_grant")

    user = db.get(User, grant.user_id)
    if user is None:
        raise HTTPException(status_code=400, detail="invalid_grant")

    return _issue_grant_response(db, user, client_id)


def _exchange_refresh_token(db: Session, refresh_token: str | None, client_id: str | None) -> TokenGrantResponse:
    if not refresh_token or not client_id:
        raise HTTPException(status_code=400, detail="invalid_request")

    result = rotate_refresh_token(db, raw_token=refresh_token, client_id=client_id)
    if result is None:
        raise HTTPException(status_code=400, detail="invalid_grant")
    user_id, new_refresh_token = result

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=400, detail="invalid_grant")

    access_token = create_access_token(user.id, user.role, expires_minutes=settings.oauth_access_token_ttl_minutes)
    return TokenGrantResponse(
        access_token=access_token,
        expires_in=settings.oauth_access_token_ttl_minutes * 60,
        refresh_token=new_refresh_token,
    )


def _issue_grant_response(db: Session, user: User, client_id: str) -> TokenGrantResponse:
    access_token = create_access_token(user.id, user.role, expires_minutes=settings.oauth_access_token_ttl_minutes)
    refresh_token_value = issue_refresh_token(db, user_id=user.id, client_id=client_id)
    return TokenGrantResponse(
        access_token=access_token,
        expires_in=settings.oauth_access_token_ttl_minutes * 60,
        refresh_token=refresh_token_value,
    )
