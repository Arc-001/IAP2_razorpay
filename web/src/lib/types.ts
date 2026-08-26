// Mirrors api/app/schemas/orchestrator.py, api/app/schemas/payment.py,
// api/app/schemas/audit.py, and api/app/orchestrator/{state,tools}.py exactly.

export type AgentState =
  | 'DRAFTING_INTENT'
  | 'AWAITING_INTENT_OK'
  | 'BUILDING_CART'
  | 'AWAITING_CART_OK'
  | 'EXECUTING_PAYMENT'
  | 'PAYMENT_FAILED'
  | 'TERMINAL'

// Raw OpenAI-chat-completions-style message. Opaque passthrough — the
// frontend only ever appends to this array and resends it, never reads
// individual fields off it for display (see ChatPanel / ToolCallCard).
export interface ChatMessage {
  role: 'user' | 'assistant' | 'tool' | 'system'
  content?: string | null
  [key: string]: unknown
}

export interface ToolCall {
  tool: string
  args: Record<string, unknown>
  output: Record<string, unknown>
}

export interface ChatRequest {
  message: string
  customer_id?: string
  intent_id?: string
  cart_id?: string
  payment_id?: string
  history: ChatMessage[]
}

export interface ChatResponse {
  state: AgentState
  reply: string
  customer_id: string | null
  intent_id: string | null
  cart_id: string | null
  payment_id: string | null
  tool_calls: ToolCall[]
  new_messages: ChatMessage[]
}

export interface PaymentMandateOut {
  id: string
  cart_mandate_id: string
  razorpay_ref: string | null
  amount: number
  status: 'pending' | 'executed' | 'failed' | 'cancelled'
  razorpay_payment_id: string | null
  signature_verified: boolean
  created_at: string
  resolved_at: string | null
}

export interface AuditLogEntry {
  id: string
  mandate_type: string
  mandate_id: string
  from_state: string | null
  to_state: string | null
  actor: string | null
  payload_hash: string | null
  created_at: string
}

export interface TransactionAuditOut {
  intent_id: string
  intent_status: string
  cart_ids: string[]
  payment_ids: string[]
  entries: AuditLogEntry[]
}

// --- Per-tool output shapes (tool_calls[i].output), by tool_calls[i].tool ---

export interface ProposeIntentOutput {
  id: string
  status: string
  structured: {
    product_query: string
    quantity: number
    budget_paise: number | null
    constraints: string[]
  }
}

export interface ConfirmIntentOutput {
  status: string
  signature: string | null
}

export interface CatalogProduct {
  id: string
  name: string
  price: number
  description: string | null
  merchant_id: string
  merchant_name: string
}

export interface SearchCatalogOutput {
  products: CatalogProduct[]
}

export interface UpsellCandidate {
  id: string
  name: string
  price: number
  description: string | null
}

export interface SuggestUpsellOutput {
  candidates: UpsellCandidate[]
}

export interface AcceptUpsellOutput {
  accepted: true
  product_id: string
  name: string
  price: number
  quantity: number
}

export interface DeclineUpsellOutput {
  accepted: false
}

export interface CartLineItem {
  product_id: string
  name: string
  unit_price: number
  quantity: number
  line_total: number
}

export interface ProposeCartOutput {
  id: string
  items: CartLineItem[]
  total_amount: number
  shipping_address: Record<string, unknown> | null
  status: string
}

export interface ConfirmCartOutput {
  status: string
  signature: string | null
  total_amount: number
}

export interface ClientPayload {
  key_id: string
  order_id: string
  amount: number
  currency: string
}

export interface CreatePaymentOutput {
  id: string
  status: string
  client_payload: ClientPayload
}

export interface CheckPaymentStatusOutput {
  status: string
  razorpay_payment_id: string | null
}

export interface CancelPaymentOutput {
  status: string
}

export interface ErrorOutput {
  error: string
}

// UI-only display log — built by the frontend itself, never sent to the
// backend (that's what `history` is for). One entry per turn.
export interface DisplayEntry {
  role: 'user' | 'assistant'
  text: string
  toolCalls?: ToolCall[]
  /** true if this assistant turn didn't advance the mandate state — used
   * for the lightweight "bounded-check rejection" visual cue. */
  stalled?: boolean
}

export function formatPaise(paise: number): string {
  return '₹' + (paise / 100).toLocaleString('en-IN')
}
