import type {
  Address,
  AddressInput,
  ChatRequest,
  ChatResponse,
  ConversationDetail,
  ConversationSummary,
  MerchantProduct,
  MerchantProductInput,
  OrderSummary,
  PaymentMandateOut,
  Profile,
  TokenResponse,
  TransactionAuditOut,
} from './types'
import { getStoredToken, useAuthStore } from '@/stores/auth'
import router from '@/router'

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

/** A 401 on an authenticated request means the session is gone (expired,
 * revoked, server restarted with a new secret) — handled once, here, rather
 * than duplicated in every caller. Login/register calls opt out (`authed:
 * false`): a wrong password there is an expected user-facing error, not a
 * dead session. */
async function handleResponse<T>(res: Response, authed: boolean): Promise<T> {
  if (authed && res.status === 401) {
    useAuthStore().logout()
    router.push('/login')
  }
  if (!res.ok) throw new ApiError(res.status, await res.text())
  return res.json() as Promise<T>
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: authHeaders() })
  return handleResponse<T>(res, true)
}

async function post<T>(path: string, body: unknown, authed: boolean): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(authed ? authHeaders() : {}) },
    body: JSON.stringify(body),
  })
  return handleResponse<T>(res, authed)
}

async function patch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
  return handleResponse<T>(res, true)
}

async function del(path: string): Promise<void> {
  const res = await fetch(`${BASE}${path}`, { method: 'DELETE', headers: authHeaders() })
  if (res.status === 401) {
    useAuthStore().logout()
    router.push('/login')
  }
  if (!res.ok) throw new ApiError(res.status, await res.text())
}

export function postChat(req: ChatRequest): Promise<ChatResponse> {
  return post('/api/chat', req, true)
}

export function login(email: string, password: string): Promise<TokenResponse> {
  return post('/api/auth/login', { email, password }, false)
}

export function approveOAuthAuthorization(requestId: string): Promise<{ redirect_to: string }> {
  return post(`/oauth/authorize/${requestId}/approve`, {}, true)
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

export function getAllTransactions(): Promise<TransactionAuditOut[]> {
  return get('/api/audit/transactions')
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

export function getMyOrders(): Promise<OrderSummary[]> {
  return get('/api/me/orders')
}

export function getMerchantProducts(): Promise<MerchantProduct[]> {
  return get('/api/merchant/products')
}

export function createMerchantProduct(input: MerchantProductInput): Promise<MerchantProduct> {
  return post('/api/merchant/products', input, true)
}

export function updateMerchantProduct(
  productId: string,
  fields: Partial<MerchantProductInput>,
): Promise<MerchantProduct> {
  return patch(`/api/merchant/products/${productId}`, fields)
}

export function deleteMerchantProduct(productId: string): Promise<void> {
  return del(`/api/merchant/products/${productId}`)
}
