import { defineStore } from 'pinia'
import { postChat, getConversation, ApiError } from '@/lib/api'
import { useAuthStore } from '@/stores/auth'
import router from '@/router'
import type { AgentState, ChatMessage, DisplayEntry } from '@/lib/types'

interface PersistedShape {
  conversationId: string | null
  history: ChatMessage[]
  displayLog: DisplayEntry[]
  customerId: string | null
  intentId: string | null
  cartId: string | null
  paymentId: string | null
  state: AgentState | null
}

/** Namespaced per logged-in account — a shared browser must not let one
 * user's cached conversation bleed into another's session. */
function storageKey(): string {
  const auth = useAuthStore()
  return `ap2_chat_session_v1:${auth.user?.id ?? 'anonymous'}`
}

function loadPersisted(): PersistedShape | null {
  try {
    const raw = localStorage.getItem(storageKey())
    if (!raw) return null
    return JSON.parse(raw) as PersistedShape
  } catch {
    return null
  }
}

function emptyState(): PersistedShape {
  return {
    conversationId: null,
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
      const { conversationId, history, displayLog, customerId, intentId, cartId, paymentId, state } = this
      const snapshot: PersistedShape = {
        conversationId,
        history,
        displayLog,
        customerId,
        intentId,
        cartId,
        paymentId,
        state,
      }
      localStorage.setItem(storageKey(), JSON.stringify(snapshot))
    },

    startOver() {
      Object.assign(this, emptyState())
      this.error = null
      localStorage.removeItem(storageKey())
    },

    /** Resume a past conversation by fetching its exact stored transcript —
     * the local cache becomes a copy of server state, not the other way
     * around (the server is the source of truth for anything resumable). */
    async loadConversation(conversationId: string) {
      this.isSending = true
      this.error = null
      try {
        const conversation = await getConversation(conversationId)
        this.conversationId = conversation.id
        this.history = conversation.history
        this.displayLog = conversation.display_log
        this.intentId = conversation.intent_id
        this.cartId = conversation.cart_id
        this.paymentId = conversation.payment_id
        this.state = conversation.state
        this.persist()
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          useAuthStore().logout()
          router.push('/login')
        } else {
          this.error = 'Could not load that conversation.'
        }
      } finally {
        this.isSending = false
      }
    },

    async sendMessage(text: string) {
      this.displayLog.push({ role: 'user', text })
      this.isSending = true
      this.error = null

      const stateBefore = this.state

      try {
        const response = await postChat({
          message: text,
          conversation_id: this.conversationId ?? undefined,
          intent_id: this.intentId ?? undefined,
          cart_id: this.cartId ?? undefined,
          payment_id: this.paymentId ?? undefined,
          history: this.history,
        })

        this.conversationId = response.conversation_id
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
        if (err instanceof ApiError && err.status === 401) {
          useAuthStore().logout()
          router.push('/login')
        } else {
          this.error = err instanceof ApiError ? err.message : 'Could not reach the server. Please try again.'
        }
      } finally {
        this.isSending = false
      }
    },
  },
})
