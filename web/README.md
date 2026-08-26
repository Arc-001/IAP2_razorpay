# AP2 Agentic Commerce — Customer Chat Frontend

Vue 3 + Vite + Tailwind SPA for the website surface (CLAUDE.md §9). Talks to
the FastAPI backend in `../api` entirely through `POST /api/chat` — this app
has no business logic of its own, it's a thin client over the orchestrator.

Deliberate deviation from CLAUDE.md's stated Next.js choice: built in Vue
instead (no SSR/SEO need here — client-only SPA against a separate API).

## Setup

```bash
npm install
cp .env.example .env.local   # point VITE_API_BASE_URL at your backend
npm run dev                  # http://localhost:5173
```

Backend must be running separately (`cd ../api && uv run uvicorn app.main:app --port 8123`)
with `cors_origins` in `api/app/config.py` including this app's origin.

## Structure

- `src/lib/api.ts` — the only place that calls the backend (`postChat`, `getPaymentStatus`, `getAuditTrail`).
- `src/lib/types.ts` — TS types mirroring the backend's Pydantic schemas exactly.
- `src/stores/conversation.ts` — Pinia store holding the conversation. Stateless-per-turn design: this store owns the full `history` array and mandate ids, persisted to `localStorage` so a refresh doesn't lose the conversation.
- `src/components/ToolCallCard.vue` — renders each orchestrator tool call as a specialized card (product results, upsell offer, cart summary, mandate signatures, Razorpay checkout, payment status); falls back to raw JSON for anything unrecognized.
- `src/components/MandateStepper.vue` + `AuditTrail.vue` — the "visibly staged" mandate chain (CLAUDE.md §11 P4.2): Intent → Cart → Payment → Outcome, plus a live view of the audit log for the current transaction.
- `src/lib/razorpay.ts` + `RazorpayCheckoutButton.vue` — lazy-loads Razorpay Checkout.js only when a payment is ready, never at app startup.

## Test-mode payment triggers

(From this project's own earlier live testing — generic Razorpay docs cards don't all work on this account.)

- **Success:** card `5267 3181 8797 5449` (Mastercard) or `4386 2894 0766 0153` (Visa), any future expiry/CVV.
- **Deterministic failure:** use a real test card, then enter an invalid/short OTP (fewer than 4 digits) at the OTP step.
