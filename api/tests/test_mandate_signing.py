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
    tampered = signature[:-1] + ("A" if signature[-1] != "A" else "B")

    with pytest.raises(jwt.exceptions.InvalidSignatureError):
        verify_mandate(tampered)
