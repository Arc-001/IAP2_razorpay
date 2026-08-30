import uuid
from datetime import timedelta

import app.services.oauth as oauth_module
from app.models import User
from app.services.oauth import (
    consume_authorization_code,
    consume_pending_request,
    create_pending_request,
    issue_authorization_code,
    issue_refresh_token,
    rotate_refresh_token,
    verify_pkce,
)
from app.services.password import hash_password


def _user(db_session) -> User:
    user = User(email=f"{uuid.uuid4()}@example.com", password_hash=hash_password("x"), role="admin")
    db_session.add(user)
    db_session.commit()
    return user


def test_verify_pkce_accepts_matching_verifier():
    # Known S256 test vector from RFC 7636 appendix B.
    verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    challenge = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    assert verify_pkce(verifier, challenge) is True


def test_verify_pkce_rejects_wrong_verifier():
    assert verify_pkce("wrong-verifier", "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM") is False


def test_pending_request_is_single_use():
    request_id = create_pending_request(
        client_id="c1", redirect_uri="http://localhost:9999/callback", state="s", code_challenge="ch"
    )

    first = consume_pending_request(request_id)
    second = consume_pending_request(request_id)

    assert first is not None
    assert first.client_id == "c1"
    assert second is None


def test_pending_request_expiry(monkeypatch):
    monkeypatch.setattr(oauth_module, "_ttl", lambda: timedelta(seconds=-1))
    request_id = create_pending_request(client_id="c1", redirect_uri="r", state="s", code_challenge="ch")

    assert consume_pending_request(request_id) is None


def test_authorization_code_is_single_use():
    user_id = uuid.uuid4()
    code = issue_authorization_code(
        user_id=user_id, client_id="c1", redirect_uri="http://localhost:9999/callback", code_challenge="ch"
    )

    first = consume_authorization_code(code)
    second = consume_authorization_code(code)

    assert first is not None
    assert first.user_id == user_id
    assert second is None


def test_authorization_code_expiry(monkeypatch):
    monkeypatch.setattr(oauth_module, "_ttl", lambda: timedelta(seconds=-1))
    code = issue_authorization_code(user_id=uuid.uuid4(), client_id="c1", redirect_uri="r", code_challenge="ch")

    assert consume_authorization_code(code) is None


def test_refresh_token_rotation_invalidates_the_old_token(db_session):
    user = _user(db_session)
    raw = issue_refresh_token(db_session, user_id=user.id, client_id="c1")

    result = rotate_refresh_token(db_session, raw_token=raw, client_id="c1")
    assert result is not None
    rotated_user_id, new_raw = result
    assert rotated_user_id == user.id
    assert new_raw != raw

    # Replaying the now-revoked old token must fail.
    assert rotate_refresh_token(db_session, raw_token=raw, client_id="c1") is None

    # But the new token from rotation works.
    second_result = rotate_refresh_token(db_session, raw_token=new_raw, client_id="c1")
    assert second_result is not None


def test_refresh_token_rejects_unknown_token(db_session):
    assert rotate_refresh_token(db_session, raw_token="not-a-real-token", client_id="c1") is None


def test_refresh_token_rejects_wrong_client(db_session):
    user = _user(db_session)
    raw = issue_refresh_token(db_session, user_id=user.id, client_id="c1")

    assert rotate_refresh_token(db_session, raw_token=raw, client_id="different-client") is None
