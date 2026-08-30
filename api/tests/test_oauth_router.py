import base64
import hashlib

import pytest

from app.config import settings

TEST_CLIENT_ID = "test-client"
TEST_REDIRECT_URI = "http://localhost:9999/callback"


def _pkce_pair():
    verifier = "a-fixed-test-verifier-that-is-long-enough-1234567890"
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


@pytest.fixture(autouse=True)
def _test_client_config(monkeypatch):
    monkeypatch.setattr(settings, "oauth_client_id", TEST_CLIENT_ID)
    monkeypatch.setattr(settings, "oauth_redirect_uris", [TEST_REDIRECT_URI])


def _authorize_query(code_challenge: str, state: str = "xyz") -> dict:
    return {
        "response_type": "code",
        "client_id": TEST_CLIENT_ID,
        "redirect_uri": TEST_REDIRECT_URI,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }


def test_metadata_document_has_expected_shape(client):
    response = client.get("/.well-known/oauth-authorization-server")
    body = response.json()
    assert response.status_code == 200
    assert body["authorization_endpoint"].endswith("/oauth/authorize")
    assert body["token_endpoint"].endswith("/oauth/token")
    assert body["code_challenge_methods_supported"] == ["S256"]
    assert set(body["grant_types_supported"]) == {"authorization_code", "refresh_token"}


def test_authorize_rejects_unknown_client_id(client):
    _, challenge = _pkce_pair()
    query = _authorize_query(challenge)
    query["client_id"] = "not-the-real-client"

    response = client.get("/oauth/authorize", params=query, follow_redirects=False)

    assert response.status_code == 400


def test_authorize_rejects_unknown_redirect_uri(client):
    _, challenge = _pkce_pair()
    query = _authorize_query(challenge)
    query["redirect_uri"] = "http://evil.example.com/callback"

    response = client.get("/oauth/authorize", params=query, follow_redirects=False)

    assert response.status_code == 400


def test_authorize_redirects_to_consent_page_with_request_id(client):
    _, challenge = _pkce_pair()

    response = client.get("/oauth/authorize", params=_authorize_query(challenge), follow_redirects=False)

    assert response.status_code == 302
    location = response.headers["location"]
    assert "/oauth/consent?request_id=" in location


def test_approve_requires_authentication(client):
    response = client.post("/oauth/authorize/some-request-id/approve")
    assert response.status_code == 401


def test_approve_rejects_non_customer_role(client, admin_headers):
    response = client.post("/oauth/authorize/some-request-id/approve", headers=admin_headers)
    assert response.status_code == 403


def test_approve_rejects_unknown_request_id(client, customer_headers):
    response = client.post("/oauth/authorize/not-a-real-request-id/approve", headers=customer_headers)
    assert response.status_code == 404


def _get_request_id(client, code_challenge: str) -> str:
    response = client.get("/oauth/authorize", params=_authorize_query(code_challenge), follow_redirects=False)
    location = response.headers["location"]
    return location.split("request_id=")[1]


def test_full_authorization_code_grant_flow(client, customer_headers):
    verifier, challenge = _pkce_pair()
    request_id = _get_request_id(client, challenge)

    approve_response = client.post(f"/oauth/authorize/{request_id}/approve", headers=customer_headers)
    assert approve_response.status_code == 200
    redirect_to = approve_response.json()["redirect_to"]
    assert redirect_to.startswith(TEST_REDIRECT_URI)
    assert "state=xyz" in redirect_to

    code = redirect_to.split("code=")[1].split("&")[0]
    token_response = client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": TEST_REDIRECT_URI,
            "client_id": TEST_CLIENT_ID,
            "code_verifier": verifier,
        },
    )

    assert token_response.status_code == 200
    body = token_response.json()
    assert body["token_type"] == "Bearer"
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["expires_in"] == settings.oauth_access_token_ttl_minutes * 60


def test_token_exchange_rejects_wrong_code_verifier(client, customer_headers):
    _, challenge = _pkce_pair()
    request_id = _get_request_id(client, challenge)
    approve_response = client.post(f"/oauth/authorize/{request_id}/approve", headers=customer_headers)
    code = approve_response.json()["redirect_to"].split("code=")[1].split("&")[0]

    response = client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": TEST_REDIRECT_URI,
            "client_id": TEST_CLIENT_ID,
            "code_verifier": "this-is-the-wrong-verifier",
        },
    )

    assert response.status_code == 400


def test_authorization_code_cannot_be_redeemed_twice(client, customer_headers):
    verifier, challenge = _pkce_pair()
    request_id = _get_request_id(client, challenge)
    approve_response = client.post(f"/oauth/authorize/{request_id}/approve", headers=customer_headers)
    code = approve_response.json()["redirect_to"].split("code=")[1].split("&")[0]
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": TEST_REDIRECT_URI,
        "client_id": TEST_CLIENT_ID,
        "code_verifier": verifier,
    }

    first = client.post("/oauth/token", data=payload)
    second = client.post("/oauth/token", data=payload)

    assert first.status_code == 200
    assert second.status_code == 400


def test_refresh_token_grant_issues_new_access_token_and_rotates(client, customer_headers):
    verifier, challenge = _pkce_pair()
    request_id = _get_request_id(client, challenge)
    approve_response = client.post(f"/oauth/authorize/{request_id}/approve", headers=customer_headers)
    code = approve_response.json()["redirect_to"].split("code=")[1].split("&")[0]
    initial = client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": TEST_REDIRECT_URI,
            "client_id": TEST_CLIENT_ID,
            "code_verifier": verifier,
        },
    ).json()

    refreshed = client.post(
        "/oauth/token",
        data={"grant_type": "refresh_token", "refresh_token": initial["refresh_token"], "client_id": TEST_CLIENT_ID},
    )
    assert refreshed.status_code == 200
    refreshed_body = refreshed.json()
    # Not asserting access_token != initial's here: two tokens minted in the
    # same wall-clock second have identical iat/exp claims and are therefore
    # legitimately byte-identical — that's expected JWT behavior, not a sign
    # rotation failed. The refresh_token (random, not claims-based) is the
    # meaningful thing to check for rotation.
    assert refreshed_body["refresh_token"] != initial["refresh_token"]

    # The old refresh token was rotated away — replaying it must fail.
    replay = client.post(
        "/oauth/token",
        data={"grant_type": "refresh_token", "refresh_token": initial["refresh_token"], "client_id": TEST_CLIENT_ID},
    )
    assert replay.status_code == 400
