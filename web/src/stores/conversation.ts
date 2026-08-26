import { defineStore } from 'pinia'
import { postChat, ApiError } from '@/lib/api'
import type { AgentState, ChatMessage, DisplayEntry } from '@/lib/types'

const STORAGE_KEY = 'ap2_chat_session_v1'

interface PersistedShape {
  history: ChatMessage[]
  displayLog: DisplayEntry[]
  customerId: string | null
  intentId: string | null
  cartId: string | null
  paymentId: string | null
  state: AgentState | null
}

function loadPersisted(): PersistedShape | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    return JSON.parse(raw) as PersistedShape
  } catch {
    return null
  }
}

function emptyState(): PersistedShape {
  return {
    history: [],
    displayLog: [],
    customerId: null,
    intentId: null,
    cartId: null,
    paymentId: null,
    state: null,
  }
}

export const useConversationStore = defineStore('conversation', {
  state: (): PersistedShape & { isSending: boolean; error: string | null } => ({
    ...(loadPersisted() ?? emptyState()),
    isSending: false,
    error: null,
  }),

  actions: {
    persist() {
      const { history, displayLog, customerId, intentId, cartId, paymentId, state } = this
      const snapshot: PersistedShape = { history, displayLog, customerId, intentId, cartId, paymentId, state }
      localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot))
    },

    startOver() {
      Object.assign(this, emptyState())
      this.error = null
      localStorage.removeItem(STORAGE_KEY)
    },

    async sendMessage(text: string) {
      this.displayLog.push({ role: 'user', text })
      this.isSending = true
      this.error = null

      const stateBefore = this.state

      try {
        const response = await postChat({
          message: text,
          customer_id: this.customerId ?? undefined,
          intent_id: this.intentId ?? undefined,
          cart_id: this.cartId ?? undefined,
          payment_id: this.paymentId ?? undefined,
          history: this.history,
        })

        if (response.customer_id) this.customerId = response.customer_id
        if (response.intent_id) this.intentId = response.intent_id
        if (response.cart_id) this.cartId = response.cart_id
        if (response.payment_id) this.paymentId = response.payment_id
        this.state = response.state
        this.history.push(...response.new_messages)
        this.displayLog.push({
          role: 'assistant',
          text: response.reply,
          toolCalls: response.tool_calls,
          stalled: response.tool_calls.length === 0 && stateBefore !== null && stateBefore === response.state,
        })
        this.persist()
      } catch (err) {
        this.error = err instanceof ApiError ? err.message : 'Could not reach the server. Please try again.'
      } finally {
        this.isSending = false
      }
    },
  },
})
