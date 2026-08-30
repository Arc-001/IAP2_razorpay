"""Request/response DTOs for the MCP server's OAuth connector flow (see plan
"Add real OAuth to the MCP server"). /oauth/token itself uses Form(...)
parameters, not a body model — it's a standard OAuth token endpoint, which
per spec is application/x-www-form-urlencoded, not JSON."""

from pydantic import BaseModel


class ApproveResponse(BaseModel):
    """POST /oauth/authorize/{request_id}/approve's response — the frontend
    navigates the browser to redirect_to itself; this endpoint never issues
    an HTTP redirect directly, since it's a JSON API call from the SPA, not
    a browser navigation."""

    redirect_to: str


class TokenGrantResponse(BaseModel):
    """POST /oauth/token's response for both grant types — standard OAuth
    token response shape, distinct from schemas/auth.py's TokenResponse
    (which wraps {access_token, user} for the website's own login, not the
    OAuth spec's {access_token, token_type, expires_in, refresh_token})."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    refresh_token: str
