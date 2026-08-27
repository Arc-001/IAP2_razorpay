import type { ChatRequest, ChatResponse, PaymentMandateOut, TokenResponse, TransactionAuditOut } from './types'
import { getStoredToken } from '@/stores/auth'

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

function authHeaders(): Record<string, string> {
  const token = getStoredToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: authHeaders() })
  if (!res.ok) throw new ApiError(res.status, await res.text())
  return res.json() as Promise<T>
}

async function post<T>(path: string, body: unknown, auth: boolean): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(auth ? authHeaders() : {}) },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new ApiError(res.status, await res.text())
  return res.json() as Promise<T>
}

export function postChat(req: ChatRequest): Promise<ChatResponse> {
  return post('/api/chat', req, true)
}

export function login(email: string, password: string): Promise<TokenResponse> {
  return post('/api/auth/login', { email, password }, false)
}

export function register(
  email: string,
  password: string,
  role: 'customer' | 'merchant',
  name: string,
  merchant_name?: string,
): Promise<TokenResponse> {
  return post('/api/auth/register', { email, password, role, name, merchant_name }, false)
}

export function getPaymentStatus(paymentId: string): Promise<PaymentMandateOut> {
  return get(`/api/payment/${paymentId}`)
}

export function getAuditTrail(intentId: string): Promise<TransactionAuditOut> {
  return get(`/api/audit/transactions/${intentId}`)
}
