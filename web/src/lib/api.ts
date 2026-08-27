import type {
  Address,
  AddressInput,
  ChatRequest,
  ChatResponse,
  ConversationDetail,
  ConversationSummary,
  PaymentMandateOut,
  Profile,
  TokenResponse,
  TransactionAuditOut,
} from './types'
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

async function patch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new ApiError(res.status, await res.text())
  return res.json() as Promise<T>
}

async function del(path: string): Promise<void> {
  const res = await fetch(`${BASE}${path}`, { method: 'DELETE', headers: authHeaders() })
  if (!res.ok) throw new ApiError(res.status, await res.text())
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

export function getMyConversations(): Promise<ConversationSummary[]> {
  return get('/api/me/conversations')
}

export function getConversation(conversationId: string): Promise<ConversationDetail> {
  return get(`/api/me/conversations/${conversationId}`)
}

export function getMyProfile(): Promise<Profile> {
  return get('/api/me/profile')
}

export function updateMyProfile(fields: Partial<Pick<Profile, 'name' | 'contact'>>): Promise<Profile> {
  return patch('/api/me/profile', fields)
}

export function getMyAddresses(): Promise<Address[]> {
  return get('/api/me/addresses')
}

export function createAddress(input: AddressInput): Promise<Address> {
  return post('/api/me/addresses', input, true)
}

export function updateAddress(addressId: string, fields: Partial<AddressInput>): Promise<Address> {
  return patch(`/api/me/addresses/${addressId}`, fields)
}

export function deleteAddress(addressId: string): Promise<void> {
  return del(`/api/me/addresses/${addressId}`)
}
