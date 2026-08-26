import type { ChatRequest, ChatResponse, PaymentMandateOut, TransactionAuditOut } from './types'

const BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8123'

export class ApiError extends Error {
  status: number
  body: string

  constructor(status: number, body: string) {
    super(`API error ${status}: ${body}`)
    this.status = status
    this.body = body
  }
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new ApiError(res.status, await res.text())
  return res.json() as Promise<T>
}

export async function postChat(req: ChatRequest): Promise<ChatResponse> {
  const res = await fetch(`${BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) throw new ApiError(res.status, await res.text())
  return res.json() as Promise<ChatResponse>
}

export function getPaymentStatus(paymentId: string): Promise<PaymentMandateOut> {
  return get(`/api/payment/${paymentId}`)
}

export function getAuditTrail(intentId: string): Promise<TransactionAuditOut> {
  return get(`/api/audit/transactions/${intentId}`)
}
