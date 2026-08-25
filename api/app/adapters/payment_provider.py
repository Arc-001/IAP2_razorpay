"""Ports & Adapters for payments (CLAUDE.md §3.3). The orchestrator and
Mandate engine depend only on PaymentProvider — StandardCheckoutAdapter
(website, this story) and PaymentLinkAdapter (MCP surface, §11 P3.2) are
interchangeable behind it."""

from typing import Protocol

from pydantic import BaseModel


class ChargeResult(BaseModel):
    reference: str  # order_id or payment_link_id — stored in payment_mandates.razorpay_ref
    adapter: str
    client_payload: dict  # whatever the specific client surface needs to complete payment


class PaymentProvider(Protocol):
    def create_charge(self, amount: int, currency: str, notes: dict) -> ChargeResult: ...
    def verify(self, payload: dict) -> bool: ...
