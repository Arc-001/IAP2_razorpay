"""
THROWAWAY SPIKE — SCRUM-14 / CLAUDE.md §11 Phase 0.

Not part of the app. Confirms Payment Link creation + completion works in
test mode — this is the collection mechanism the MCP/Claude surface uses
(CLAUDE.md §6.2, §9), since Claude can't render the Checkout widget.

Run:
    uv run python scripts/spike_payment_link.py create
    # open the printed URL, pay with a test card (UPI is off for this
    # account per SCRUM-13 finding — see CLAUDE.md 6.9 for test cards)
    uv run python scripts/spike_payment_link.py status <payment_link_id>
"""

import sys

import razorpay

from app.config import settings

if not settings.razorpay_key_id or not settings.razorpay_key_secret:
    raise SystemExit("Set RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET in api/.env first.")

client = razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))


def create():
    link = client.payment_link.create({
        "amount": 50000,  # paise -> ₹500.00
        "currency": "INR",
        "description": "SCRUM-14 spike",
        "notes": {"mandate_id": "spike-scrum-14"},  # webhook correlation, §6.7
    })
    print(f"Payment Link created: {link['id']}")
    print(f"Status: {link['status']}")
    print(f"Open to pay: {link['short_url']}")


def status(link_id: str):
    link = client.payment_link.fetch(link_id)
    print(f"Payment Link {link_id}")
    print(f"Status: {link['status']}")
    if link.get("payments"):
        for p in link["payments"]:
            print(f"  payment_id={p['payment_id']} status={p['status']} method={p.get('method')}")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("create", "status"):
        raise SystemExit("Usage: spike_payment_link.py create | status <payment_link_id>")

    if sys.argv[1] == "create":
        create()
    else:
        if len(sys.argv) < 3:
            raise SystemExit("Usage: spike_payment_link.py status <payment_link_id>")
        status(sys.argv[2])
