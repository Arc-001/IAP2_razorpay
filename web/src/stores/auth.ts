import { defineStore } from 'pinia'
import { ApiError, login as apiLogin, register as apiRegister } from '@/lib/api'

const STORAGE_KEY = 'ap2_auth_v1'

export interface AuthUser {
  id: string
  email: string
  role: 'admin' | 'merchant' | 'customer'
  customer_id: string | null
  merchant_id: string | null
}

interface PersistedAuth {
  token: string | null
  user: AuthUser | null
}

function loadPersisted(): PersistedAuth {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return { token: null, user: null }
    return JSON.parse(raw) as PersistedAuth
  } catch {
    return { token: null, user: null }
  }
}

/** Read directly, without going through the Pinia store — lib/api.ts needs
 * the current token from outside any component/setup context. */
export function getStoredToken(): string | null {
  return loadPersisted().token
}

export const useAuthStore = defineStore('auth', {
  state: (): PersistedAuth & { error: string | null; isSubmitting: boolean } => ({
    ...loadPersisted(),
    error: null,
    isSubmitting: false,
  }),

  getters: {
    isAuthenticated: (state) => state.token !== null,
  },

  actions: {
    persist() {
      const snapshot: PersistedAuth = { token: this.token, user: this.user }
      localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot))
    },

    async login(email: string, password: string) {
      this.isSubmitting = true
      this.error = null
      try {
        const response = await apiLogin(email, password)
        this.token = response.access_token
        this.user = response.user as AuthUser
        this.persist()
        return true
      } catch (err) {
        this.error = err instanceof ApiError ? 'Incorrect email or password.' : 'Could not reach the server.'
        return false
      } finally {
        this.isSubmitting = false
      }
    },

    async register(email: string, password: string, role: 'customer' | 'merchant', name: string, merchantName?: string) {
      this.isSubmitting = true
      this.error = null
      try {
        const response = await apiRegister(email, password, role, name, merchantName)
        this.token = response.access_token
        this.user = response.user as AuthUser
        this.persist()
        return true
      } catch (err) {
        this.error =
          err instanceof ApiError && err.status === 400
            ? 'That email is already registered.'
            : 'Could not reach the server.'
        return false
      } finally {
        this.isSubmitting = false
      }
    },

    logout() {
      this.token = null
      this.user = null
      localStorage.removeItem(STORAGE_KEY)
    },
  },
})
