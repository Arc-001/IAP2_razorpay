<div align="center">

# AP2 Agentic Commerce on Razorpay

**An AI agent that can actually spend your money — and cryptographically prove you said it could.**

An implementation of Google's [Agent Payments Protocol (AP2)](https://github.com/google-agentic-commerce/AP2) over India's UPI rail, where every money-moving action is explainable, bounded, gated, and signed.

<br>

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Vue.js](https://img.shields.io/badge/Vue.js-3.5-4FC08D?style=for-the-badge&logo=vuedotjs&logoColor=white)](https://vuejs.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![MCP](https://img.shields.io/badge/MCP-Streamable_HTTP-D97757?style=for-the-badge&logo=anthropic&logoColor=white)](https://modelcontextprotocol.io/)

<br>

![Tests](https://img.shields.io/badge/tests-289_passing-success?style=flat-square&logo=pytest&logoColor=white)
![Ruff](https://img.shields.io/badge/lint-ruff-D7FF64?style=flat-square&logo=ruff&logoColor=black)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-D71F00?style=flat-square&logo=sqlalchemy&logoColor=white)
![Alembic](https://img.shields.io/badge/migrations-alembic-6BA81E?style=flat-square)
![Pydantic](https://img.shields.io/badge/Pydantic-2.9-E92063?style=flat-square&logo=pydantic&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-8-646CFF?style=flat-square&logo=vite&logoColor=white)
![Tailwind](https://img.shields.io/badge/Tailwind-4-06B6D4?style=flat-square&logo=tailwindcss&logoColor=white)
![Pinia](https://img.shields.io/badge/Pinia-4-FFD859?style=flat-square&logo=pinia&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-6.0-3178C6?style=flat-square&logo=typescript&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)
![Razorpay](https://img.shields.io/badge/Razorpay-Test_Mode-0C2451?style=flat-square&logo=razorpay&logoColor=white)
![OAuth](https://img.shields.io/badge/OAuth-2.1_+_PKCE-EB5424?style=flat-square&logo=auth0&logoColor=white)
![HMAC](https://img.shields.io/badge/signing-HMAC--SHA256-1E293B?style=flat-square&logo=letsencrypt&logoColor=white)

</div>

---

## Table of Contents

- [The Problem](#the-problem)
- [What Makes This Different](#what-makes-this-different)
- [Mandate Signing: The Core Mechanism](#mandate-signing-the-core-mechanism)
- [Architecture](#architecture)
- [Guardrails](#guardrails)
- [Two Surfaces, One Mandate Engine](#two-surfaces-one-mandate-engine)
- [Quickstart](#quickstart)
- [Demo Walkthrough](#demo-walkthrough)
- [API Reference](#api-reference)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Design Decisions](#design-decisions)
- [Roadmap](#roadmap)

---

## The Problem

Letting an AI agent hold your credit card is easy. Letting it hold your credit card *responsibly* is the entire problem.

When an agent buys something on your behalf, four questions need answers that survive a dispute:

| Question | Naive agent | This system |
|---|---|---|
| **What did the user actually ask for?** | Buried in a chat transcript | A signed **Intent Mandate** with structured constraints |
| **What exactly did they approve?** | Model's recollection | A signed **Cart Mandate** bound to that intent |
| **Could the agent have skipped a step?** | Only if the prompt held | Structurally impossible — tools are gated per state |
| **Can anyone prove it wasn't tampered with?** | No | HMAC-SHA256 signature over a canonical payload hash |

This repository implements that chain end-to-end, against real Razorpay test-mode infrastructure, on the UPI rail.

---

## What Makes This Different

**1. The mandate chain is real, not decorative.**
Most "agentic commerce" demos are a chat UI wrapped around a payments API. Here, an `intent_mandates` row is HMAC-signed and made immutable at the moment a human confirms it, and a `cart_mandates` row is signed separately and cryptographically bound to that intent. The Payment Mandate is derived from both. Break the chain, and the signature verification tells you.

**2. Guardrails are structural, not prompted.**
The agent is not *asked* to avoid skipping confirmation. The tool-calling loop physically does not expose `confirm_cart` until the state machine says it may. An illegal transition is not discouraged — it is unreachable. See [Guardrails](#guardrails).

**3. UPI rail, not cards or stablecoins.**
AP2 is deliberately payment-rail-agnostic. Nearly every reference implementation reaches for cards. This one settles over **UPI via Razorpay**, which is the rail that actually matters for the Indian market and aligns with NPCI's UAP work extending UPI Circle's delegated-payments model.

**4. Two completely different clients, one mandate engine.**
The same signing, gating, and audit logic serves both an in-house Vue chat UI *and* Claude itself, connected over a remote MCP server with a full OAuth 2.1 + PKCE flow. Not a hardcoded integration — a real authorization-code grant with refresh-token rotation. See [Two Surfaces](#two-surfaces-one-mandate-engine).

**5. The audit trail is the database, not a log file.**
`audit_log` is append-only by design. Every mandate transition is an `INSERT`, never an `UPDATE`. Reconstructing any transaction means walking Intent to Cart to Payment and replaying the rows.

**6. Failure is a first-class, demoable path.**
`failure@razorpay` triggers a deterministic failure. The agent reports it plainly, writes it to the audit log, and offers retry or cancel. It never fails silently, and it never claims success it did not verify.

---

## Mandate Signing: The Core Mechanism

### The three mandates

| Mandate | Signed when | Binds | Stored in |
|---|---|---|---|
| **Intent** | Human confirms what they want | Constraints: product query, quantity, budget cap | `intent_mandates.signature` |
| **Cart** | Human confirms the final basket | Specific SKUs, prices, shipping, total, `intent_mandate_id` | `cart_mandates.signature` |
| **Payment** | System derives at charge time | Authorized amount, Razorpay reference, webhook verification result | `payment_mandates` |

### How a signature is produced

Signing is a two-step **hash-then-sign** construction in [`api/app/services/mandate_signing.py`](api/app/services/mandate_signing.py):

```python
def hash_payload(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()

def sign_mandate(mandate_type: str, mandate_id: uuid.UUID, payload_hash: str) -> str:
    return jwt.encode(
        {"mandate_type": mandate_type, "mandate_id": str(mandate_id), "payload_hash": payload_hash},
        settings.mandate_signing_secret,
        algorithm="HS256",
    )
```

**Step 1 — canonical hash.** The mandate payload is serialized with sorted keys and no whitespace, so semantically identical data always produces byte-identical JSON, then fingerprinted with SHA-256. Without canonicalization, re-serializing the same dict in a different key order would produce a different hash and a false tamper alarm.

**Step 2 — keyed signature.** That fingerprint, plus the mandate's type and ID, is wrapped in a JWT signed with `HS256` — which is HMAC-SHA256 — keyed with a server-held secret. HMAC is a *keyed* hash: it proves both **integrity** (the content has not changed) and **authenticity** (it was issued by a holder of the secret). It is not encryption; it hides nothing. It makes tampering detectable.

### What this actually protects against

```mermaid
flowchart LR
    A["Human confirms cart<br/>total: 299900 paise"] --> B["hash_payload()<br/>SHA-256 canonical JSON"]
    B --> C["sign_mandate()<br/>HMAC-SHA256 / HS256"]
    C --> D[("cart_mandates.signature<br/>stored")]
    D --> E{"Later: verify"}
    E --> F["Recompute hash<br/>of current row"]
    F --> G{"Match?"}
    G -->|Yes| H["Untampered<br/>Human approved exactly this"]
    G -->|No| I["Tampered<br/>Row changed after signing"]

    style H fill:#0d9488,color:#fff
    style I fill:#dc2626,color:#fff
    style C fill:#1e293b,color:#fff
```

If anything — a bug, a compromised process, a malicious actor with database access — alters a confirmed cart's total from 299900 to 999900 paise, the stored `payload_hash` no longer matches a freshly computed hash of the row. The mismatch is detectable without needing a backup to diff against. That is the "tamper-evident" property AP2 requires.

### Why HMAC and not real PKI

AP2's specification envisions cryptographic signatures verifiable by **third parties** — a payment processor independently validating a user's mandate without trusting or contacting the merchant's server. That genuinely requires asymmetric cryptography: key pairs, certificate distribution, revocation, W3C Verifiable Credentials.

In this system, **our own backend is the only verifier**. No external party ever validates a mandate signature independently. Asymmetric signing's defining advantage therefore buys nothing here, while costing key generation, storage, rotation, and distribution infrastructure.

A single server-held secret delivers the identical tamper-evidence guarantee for a fraction of the engineering. This is a deliberate, documented trade-off, not an oversight — and it is the correct one at this scope. Moving to asymmetric signing later means changing one module: `mandate_signing.py`.

### Two secrets, deliberately separated

| Secret | Signs | Why separate |
|---|---|---|
| `MANDATE_SIGNING_SECRET` | Intent and Cart mandate payloads | A leaked login token must never be replayable as a forged mandate |
| `AUTH_JWT_SECRET` | HTTP session and OAuth access tokens | Rotating login sessions must not invalidate every historical mandate signature |

Same primitive, two trust boundaries, never shared. Both default to obviously-fake dev values in `config.py` and **must** be replaced in any real deployment.

---

## Architecture

<div align="center">
  <img src="architecture.png" alt="System architecture: two client surfaces feeding one FastAPI backend containing the MCP server, orchestrator, mandate engine, payment adapters and catalog repository, backed by PostgreSQL and Razorpay test mode" width="100%">
</div>

<br>

Both client surfaces converge on a **single FastAPI deployable**. Inside it, the orchestrator is the only component permitted to call across all three domain services — catalog, mandate engine, and payment adapters never call each other directly.

The dashed boundary marks the **signed and audited mandate chain**: everything crossing it is HMAC-signed and written to the append-only audit log before any money moves.

Razorpay's own hosted MCP server appears bottom-left for a reason worth stating plainly: it is used **only** as internal plumbing, from our backend, with our own keys. It is never exposed to a buyer-facing agent, because it authenticates with full merchant-account access and has no concept of a cart, catalog, or mandate — the exact opposite of bounded and gated.

**Ports and adapters for payments.** A single `PaymentProvider` interface has two concrete implementations, because the two surfaces have genuinely different constraints:

- `StandardCheckoutAdapter` — creates a Razorpay Order for the embedded Checkout widget. Requires a live browser.
- `PaymentLinkAdapter` — creates a hosted Payment Link URL. Claude has no browser to render a widget in, so it hands back a clickable link instead.

The mandate engine does not know or care which is in play.

---

## Guardrails

### State-gated tool exposure

The model is never given a tool it should not be able to call. Defined in [`api/app/orchestrator/tools.py`](api/app/orchestrator/tools.py):

```mermaid
stateDiagram-v2
    [*] --> DRAFTING_INTENT
    DRAFTING_INTENT --> AWAITING_INTENT_OK: propose_intent
    AWAITING_INTENT_OK --> BUILDING_CART: confirm_intent
    BUILDING_CART --> AWAITING_CART_OK: propose_cart
    AWAITING_CART_OK --> EXECUTING_PAYMENT: confirm_cart
    EXECUTING_PAYMENT --> TERMINAL: payment executed
    EXECUTING_PAYMENT --> PAYMENT_FAILED: payment failed
    PAYMENT_FAILED --> EXECUTING_PAYMENT: retry_payment
    PAYMENT_FAILED --> TERMINAL: cancel_payment
    TERMINAL --> [*]
```

| State | Tools exposed to the model |
|---|---|
| `DRAFTING_INTENT` | `propose_intent` |
| `AWAITING_INTENT_OK` | `propose_intent`, `confirm_intent` |
| `BUILDING_CART` | `search_catalog`, `suggest_upsell`, `accept_upsell`, `decline_upsell`, `propose_cart` |
| `AWAITING_CART_OK` | the above, plus `confirm_cart` |
| `EXECUTING_PAYMENT` | `create_payment`, `check_payment_status` |
| `PAYMENT_FAILED` | `retry_payment`, `cancel_payment`, `check_payment_status` |
| `TERMINAL` | `check_payment_status` |

State is **derived from database rows**, never stored as a mutable field — it cannot drift out of sync with reality.

> `check_payment_status` remains available in terminal states by design. It is read-only and idempotent, and an asynchronous webhook can resolve a payment *after* the model's last information. Removing it there once caused the agent to confidently report a stale "pending" for a payment that had already succeeded.

### Bounded mandate rules

| Rule | Enforcement | Default |
|---|---|---|
| **Budget cap** | `confirm_cart` raises if `cart.total_amount > intent.budget_paise` | Per-intent |
| **Intent expiry** | A stale intent cannot be used to build a cart | 15 minutes |
| **Price-rise re-confirmation** | Cart drafting refuses if a product's price rose beyond the threshold since last known, unless explicitly acknowledged | 10 percent |
| **Upsell gating** | `suggest_upsell` must resolve before the cart is presented — never added after a human approves a total | Structural |
| **Address timing** | Shipping address is collected before the cart is shown, so the approved total is final | Structural |

### Webhook trust

A payment is written as `executed` or `failed` **only after** its Razorpay webhook signature verifies. An unverified webhook is not trusted, and the agent will not claim a payment succeeded on a customer's say-so — it calls `check_payment_status` and reports exactly what the tool returns.

---

## Two Surfaces, One Mandate Engine

<table>
<tr>
<th width="50%">Website Chat</th>
<th width="50%">Claude via MCP</th>
</tr>
<tr>
<td>

Vue 3 SPA with a live mandate stepper, signature reveal, audit-trail sidebar, and embedded Razorpay Checkout.

**Orchestration:** our own tool-calling loop against OpenRouter, with per-state tool exposure.

**Payment:** `StandardCheckoutAdapter` — Razorpay Order plus the Checkout widget.

**Auth:** email and password, JWT bearer tokens.

</td>
<td>

A remote MCP server exposing 12 tools to Claude's own model, connected as a custom connector.

**Orchestration:** Claude orchestrates. Gating is enforced one layer down — every service function rejects out-of-order calls independently.

**Payment:** `PaymentLinkAdapter` — a hosted URL Claude can hand back as a link.

**Auth:** full OAuth 2.1 authorization-code flow with PKCE (S256), refresh-token rotation, and RFC 8414 / RFC 9728 discovery documents.

</td>
</tr>
</table>

The MCP server derives the caller's identity from the verified bearer token — never from a tool argument the model could get wrong or a caller could spoof.

**MCP tools:** `propose_intent`, `confirm_intent`, `search_catalog`, `suggest_upsell`, `accept_upsell`, `decline_upsell`, `propose_cart`, `confirm_cart`, `create_payment_link`, `check_payment_status`, `retry_payment`, `cancel_payment`

---

## Quickstart

### Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.12 or newer | Managed with [`uv`](https://docs.astral.sh/uv/) |
| Node.js | 20 or newer | For the Vue frontend |
| Docker | with Compose v2 | Runs PostgreSQL locally |
| Razorpay account | Test mode | [Dashboard](https://dashboard.razorpay.com/) to Account and Settings to API Keys |
| OpenRouter key | — | [openrouter.ai](https://openrouter.ai/) for the agent's model |

### 1. Clone and configure

```bash
git clone https://github.com/Arc-001/IAP2_razorpay.git
cd IAP2_razorpay
cp api/.env.example api/.env
```

Fill in `api/.env`:

```bash
# Database — port 5433, not 5432 (5432 is commonly already taken on dev hosts)
DATABASE_URL=postgresql+psycopg://ap2:ap2@localhost:5433/ap2

# Razorpay test-mode credentials
RAZORPAY_KEY_ID=rzp_test_xxxxxxxxxxxx
RAZORPAY_KEY_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx
RAZORPAY_WEBHOOK_SECRET=xxxxxxxxxxxx

# Signing secrets — generate with: openssl rand -hex 32
MANDATE_SIGNING_SECRET=<32-byte hex>
AUTH_JWT_SECRET=<a different 32-byte hex>

# Agent model, routed through OpenRouter
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxx
OPENROUTER_MODEL=google/gemini-3.7-flash
```

> **Important:** `MANDATE_SIGNING_SECRET` and `AUTH_JWT_SECRET` must be different values. Both have obviously-fake defaults in `config.py` that are safe only for local development.

### 2. Start everything

```bash
./start.sh
```

That single script brings up PostgreSQL via Docker, the FastAPI backend, and the Vite dev server, skipping anything already running. To stop:

```bash
./stop.sh
```

<details>
<summary><b>Or start each piece manually</b></summary>

```bash
# PostgreSQL
docker compose up -d postgres

# Backend
cd api
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --port 8123 --reload

# Frontend
cd web
npm install
npm run dev -- --port 5173
```

</details>

### 3. Seed data and accounts

```bash
cd api
uv run python scripts/seed_catalog.py       # Products across multiple merchants
uv run python scripts/create_demo_users.py  # One account per role
```

### 4. Open the app

| Service | URL |
|---|---|
| Website chat | http://localhost:5173 |
| API docs (Swagger) | http://localhost:8123/docs |
| Health check | http://localhost:8123/health |
| Audit trail (admin) | http://localhost:8123/audit |

**Demo accounts** — all use password `demo1234`:

| Role | Email |
|---|---|
| Customer | `customer@demo.local` |
| Merchant | `merchant@demo.local` |
| Admin | `admin@demo.local` |

### 5. Razorpay webhooks (required for payment confirmation)

Payments resolve via webhook, so Razorpay needs a public URL to reach your local backend:

```bash
cloudflared tunnel --url http://localhost:8123
```

Register the printed URL plus `/api/webhooks/razorpay` in the Razorpay Dashboard under Settings to Webhooks, subscribing to `payment.captured` and `payment.failed`.

**Test payment handles:**

| Handle | Result |
|---|---|
| `success@razorpay` | Payment succeeds |
| `failure@razorpay` | Payment fails deterministically |

<details>
<summary><b>Optional: connect Claude to the MCP server</b></summary>

```bash
cd api
uv run python mcp_server/server.py   # listens on :8124
cloudflared tunnel --url http://localhost:8124
```

Then in claude.ai, add a custom connector:

| Field | Value |
|---|---|
| URL | `https://<your-mcp-tunnel>/mcp` |
| Authentication | Always required |
| OAuth client | Use your own OAuth client |
| Client ID | `ap2-claude-connector` |
| Client secret | leave blank (public client, PKCE) |

The backend must run with `OAUTH_REDIRECT_URIS=["https://claude.ai/api/mcp/auth_callback"]` and `CORS_ORIGINS` pointing at your frontend's public URL.

</details>

---

## Demo Walkthrough

A five-minute path that exercises every guarantee this system claims:

| Step | Action | What it proves |
|---|---|---|
| 1 | Ask for a product in natural language, confirm the Intent | Intent Mandate signed and made immutable |
| 2 | Review the cart, accept or decline the upsell, confirm | Cart Mandate signed and bound to the intent |
| 3 | Pay with `success@razorpay` | Webhook verified, payment executed, audit trail populates live |
| 4 | Start again, try to exceed the stated budget | Bounded check refuses at `confirm_cart` — structurally, not by prompt |
| 5 | Pay with `failure@razorpay` | Failure branch: reported plainly, logged, retry and cancel offered |
| 6 | Repeat the purchase through Claude via the MCP connector | Same mandate engine, entirely different client, real OAuth |
| 7 | Log in as admin | Cross-customer transactions, signatures, full audit chain |

---

## API Reference

<details>
<summary><b>Authentication</b></summary>

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/api/auth/register` | None | Create a customer or merchant account |
| `POST` | `/api/auth/login` | None | Returns a JWT bearer token |
| `GET` | `/api/auth/me` | Bearer | Current user |

</details>

<details>
<summary><b>Agent and mandates</b></summary>

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/api/chat` | Customer | Main agent loop, state-gated tool calling |
| `POST` | `/api/intent/extract` | Customer | Natural language to structured intent |
| `POST` | `/api/intent` | Customer | Create a draft Intent Mandate |
| `POST` | `/api/intent/{id}/confirm` | Customer | Sign and freeze the intent |
| `POST` | `/api/cart` | Customer | Assemble a draft cart |
| `POST` | `/api/cart/{id}/confirm` | Customer | Budget check, then sign the cart |
| `POST` | `/api/payment` | Customer | Create a Razorpay charge |
| `GET` | `/api/payment/{id}` | Customer | Current payment status |
| `POST` | `/api/webhooks/razorpay` | Signature | Verified webhook receiver |

</details>

<details>
<summary><b>Catalog</b></summary>

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/api/catalog/products` | Public | List products |
| `GET` | `/api/catalog/products/{id}` | Public | Single product |
| `GET` | `/api/catalog/search` | Public | Search across every merchant |

</details>

<details>
<summary><b>Customer</b></summary>

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/api/me/profile` | Customer | Profile |
| `PATCH` | `/api/me/profile` | Customer | Update profile |
| `GET` `POST` `PATCH` `DELETE` | `/api/me/addresses` | Customer | Saved addresses |
| `GET` | `/api/me/orders` | Customer | Order history |
| `GET` | `/api/me/conversations` | Customer | Resumable chat threads |

</details>

<details>
<summary><b>Merchant</b></summary>

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/api/merchant/products` | Merchant | Own catalog |
| `POST` | `/api/merchant/products` | Merchant | Add a product, tags generated by AI |
| `PATCH` | `/api/merchant/products/{id}` | Merchant | Update, re-tags on description change |
| `DELETE` | `/api/merchant/products/{id}` | Merchant | Remove |

</details>

<details>
<summary><b>Audit and OAuth</b></summary>

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/api/audit/transactions` | Admin | Every transaction |
| `GET` | `/api/audit/transactions/{intent_id}` | Admin or owner | Full mandate chain |
| `GET` | `/audit` | Admin | Server-rendered debug view |
| `GET` | `/.well-known/oauth-authorization-server` | Public | RFC 8414 metadata |
| `GET` | `/oauth/authorize` | Public | Authorization-code entry point |
| `POST` | `/oauth/token` | Public | Token exchange and refresh |

</details>

---

## Project Structure

```
IAP2_razorpay/
├── api/
│   ├── app/
│   │   ├── adapters/          Ports and adapters for payments
│   │   │   ├── payment_provider.py     PaymentProvider interface
│   │   │   ├── standard_checkout.py    Website: Order + Checkout widget
│   │   │   └── payment_link.py         MCP: hosted Payment Link
│   │   ├── orchestrator/      Agent loop
│   │   │   ├── state.py               AgentState, derive_state()
│   │   │   ├── tools.py               TOOLS_BY_STATE gating
│   │   │   └── orchestrator.py        Tool-calling loop
│   │   ├── services/          Domain logic
│   │   │   ├── mandate_signing.py     HMAC-SHA256 signing
│   │   │   ├── intent_mandate.py      Intent lifecycle
│   │   │   ├── cart_mandate.py        Cart assembly, budget guard
│   │   │   ├── payment_mandate.py     Charge creation, retry, cancel
│   │   │   ├── payment_webhook.py     Signature-verified resolution
│   │   │   ├── audit.py               Append-only trail
│   │   │   ├── oauth.py               PKCE, codes, refresh rotation
│   │   │   └── ...
│   │   ├── repositories/      CatalogRepository
│   │   ├── routers/           FastAPI routes, thin by convention
│   │   ├── models/            SQLAlchemy ORM
│   │   ├── schemas/           Pydantic DTOs, reused as MCP tool schemas
│   │   └── dependencies/      get_current_user, require_role
│   ├── mcp_server/
│   │   ├── server.py          12 MCP tools, streamable HTTP
│   │   └── auth.py            Bearer middleware, RFC 9728 metadata
│   ├── migrations/            Alembic
│   ├── scripts/               Seeding, spikes, live tests
│   └── tests/                 289 tests
├── web/
│   └── src/
│       ├── views/             Login, chat, history, profile, orders,
│       │                      merchant catalog, admin, OAuth consent
│       ├── components/        Mandate stepper, signature reveal,
│       │                      audit trail, upsell, checkout button
│       ├── stores/            Pinia: auth, conversation
│       └── lib/               API client, markdown, types
├── docker-compose.yml
├── start.sh
└── stop.sh
```

---

## Testing

```bash
cd api
uv run pytest                                    # 289 tests
uv run pytest tests/test_orchestrator.py -v      # One file
uv run ruff check app migrations mcp_server tests
```

Tests run against a real PostgreSQL instance — each test executes inside a transaction that is rolled back afterward, so no test leaves state behind or touches the development database.

Coverage spans mandate signing and verification, state derivation and tool gating, budget and expiry and price-rise guards, webhook signature verification, the failure and retry branch, RBAC ownership boundaries, OAuth PKCE and single-use codes and refresh rotation, and MCP bearer authentication.

---

<div align="center">

Built for the Razorpay hackathon, Track 1: AI Growth and Agentic Commerce.

**Every money-moving action here is explainable, bounded, gated, audited, and signed.**

</div>
