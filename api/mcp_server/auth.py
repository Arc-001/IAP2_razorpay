"""Bearer-token auth for the MCP server's HTTP transport.

Deliberately NOT FastMCP's built-in OAuth resource-server subsystem
(`token_verifier`/`AuthSettings`) — that requires standing up real OAuth
machinery (issuer_url, discovery metadata, optionally dynamic client
registration) just to hand out tokens we already issue elsewhere. Same call
CLAUDE.md §1 already made for mandate signing ("don't build real PKI, HMAC/
JWT is enough") applies here: this is a plain ASGI middleware that verifies
the exact same bearer token `/api/auth/login` already issues, using the
exact same `decode_access_token` the REST API uses.

A pure ASGI middleware (not Starlette's BaseHTTPMiddleware) on purpose —
streamable-http responses are streamed (SSE-style), and BaseHTTPMiddleware
buffers the whole response body before forwarding it, which breaks that.
"""

import jwt
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.db import SessionLocal
from app.models import User
from app.services.auth_tokens import decode_access_token


class BearerAuthMiddleware:
    """Verifies Authorization: Bearer <token> on every HTTP request, and
    stashes the resulting customer_id on scope["state"] for tools to read
    via `ctx.request_context.request.state.customer_id`. This server is
    buyer-facing only (see server.py's module docstring) — non-customer
    tokens are rejected outright, not silently scoped down."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        token = _extract_bearer_token(scope)
        if token is None:
            await JSONResponse({"error": "not authenticated"}, status_code=401)(scope, receive, send)
            return

        try:
            payload = decode_access_token(token)
        except jwt.PyJWTError:
            await JSONResponse({"error": "invalid or expired token"}, status_code=401)(scope, receive, send)
            return

        db = SessionLocal()
        try:
            user = db.get(User, payload["sub"])
        finally:
            db.close()

        if user is None:
            await JSONResponse({"error": "user no longer exists"}, status_code=401)(scope, receive, send)
            return
        if user.role != "customer":
            await JSONResponse(
                {"error": "this MCP server is customer-only"}, status_code=403
            )(scope, receive, send)
            return

        scope.setdefault("state", {})
        scope["state"]["customer_id"] = str(user.customer_id)
        scope["state"]["user_id"] = str(user.id)

        await self.app(scope, receive, send)


def _extract_bearer_token(scope: Scope) -> str | None:
    for name, value in scope.get("headers", []):
        if name.decode("latin-1").lower() == "authorization":
            header = value.decode("latin-1")
            if header.lower().startswith("bearer "):
                return header[7:]
    return None
