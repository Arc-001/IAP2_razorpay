import uuid

import jwt
import pytest

from app.services.mandate_signing import hash_payload, sign_mandate, verify_mandate


def test_hash_payload_is_deterministic_regardless_of_key_order():
    a = hash_payload({"budget_paise": 500, "product_query": "cable"})
    b = hash_payload({"product_query": "cable", "budget_paise": 500})
    assert a == b


def test_hash_payload_differs_for_different_content():
    a = hash_payload({"product_query": "cable"})
    b = hash_payload({"product_query": "charger"})
    assert a != b


def test_sign_and_verify_roundtrip():
    mandate_id = uuid.uuid4()
    payload_hash = hash_payload({"product_query": "cable"})

    signature = sign_mandate("intent", mandate_id, payload_hash)
    claims = verify_mandate(signature)

    assert claims["mandate_type"] == "intent"
    assert claims["mandate_id"] == str(mandate_id)
    assert claims["payload_hash"] == payload_hash


def test_verify_rejects_tampered_signature():
    signature = sign_mandate("intent", uuid.uuid4(), hash_payload({"a": 1}))
    header_and_payload, sig = signature.rsplit(".", 1)

    # Flip a character in the middle of the signature, not the last one: a
    # 32-byte HMAC-SHA256 signature doesn't divide evenly into base64's
    # 6-bit groups, so the final character carries unused padding bits —
    # changing only it can occasionally decode to the *same* underlying
    # bytes, which isn't actually tampering.
    mid = len(sig) // 2
    flipped = "A" if sig[mid] != "A" else "B"
    tampered = f"{header_and_payload}.{sig[:mid]}{flipped}{sig[mid + 1:]}"

    with pytest.raises(jwt.exceptions.PyJWTError):
        verify_mandate(tampered)
