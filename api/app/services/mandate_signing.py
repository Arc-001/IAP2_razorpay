"""HMAC-SHA256 mandate signing (CLAUDE.md §1: "no real PKI / W3C Verifiable
Credentials" — HS256 with a server-held secret is sufficient). Shared by
Intent and Cart mandates."""

import hashlib
import json
import uuid

import jwt

from app.config import settings


def hash_payload(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def sign_mandate(mandate_type: str, mandate_id: uuid.UUID, payload_hash: str) -> str:
    return jwt.encode(
        {"mandate_type": mandate_type, "mandate_id": str(mandate_id), "payload_hash": payload_hash},
        settings.mandate_signing_secret,
        algorithm="HS256",
    )


def verify_mandate(signature: str) -> dict:
    return jwt.decode(signature, settings.mandate_signing_secret, algorithms=["HS256"])
