"""HTTP-auth JWT (login sessions) — deliberately a separate secret/purpose
from app/services/mandate_signing.py's mandate-signing JWT. A leaked login
token should never be replayable against mandate-verification code, and
rotating one secret shouldn't force rotating the other."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt

from app.config import settings


def create_access_token(user_id: uuid.UUID, role: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.auth_jwt_expires_minutes),
    }
    return jwt.encode(payload, settings.auth_jwt_secret, algorithm=settings.auth_jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Raises jwt.PyJWTError (expired, malformed, bad signature) on failure —
    callers translate that into a 401, never trust a token that fails this."""
    return jwt.decode(token, settings.auth_jwt_secret, algorithms=[settings.auth_jwt_algorithm])
