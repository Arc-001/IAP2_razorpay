import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.config import settings
from app.services.auth_tokens import create_access_token, decode_access_token


def test_create_and_decode_roundtrip():
    user_id = uuid.uuid4()
    token = create_access_token(user_id, "customer")

    claims = decode_access_token(token)

    assert claims["sub"] == str(user_id)
    assert claims["role"] == "customer"


def test_decode_rejects_expired_token():
    user_id = uuid.uuid4()
    now = datetime.now(UTC)
    expired = jwt.encode(
        {"sub": str(user_id), "role": "customer", "iat": now - timedelta(hours=2), "exp": now - timedelta(hours=1)},
        settings.auth_jwt_secret,
        algorithm=settings.auth_jwt_algorithm,
    )

    with pytest.raises(jwt.PyJWTError):
        decode_access_token(expired)


def test_decode_rejects_token_signed_with_a_different_secret():
    token = jwt.encode({"sub": "x", "role": "customer"}, "some-other-secret", algorithm="HS256")

    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token)


def test_decode_rejects_mandate_signing_token():
    """The two JWT secrets/purposes must not be interchangeable — a mandate
    signature should never double as a login session token."""
    from app.services.mandate_signing import sign_mandate

    mandate_token = sign_mandate("intent", uuid.uuid4(), "somehash")

    with pytest.raises(jwt.PyJWTError):
        decode_access_token(mandate_token)
