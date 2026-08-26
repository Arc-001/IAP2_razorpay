import { ref } from 'vue'
import { getPaymentStatus } from '@/lib/api'
import { useConversationStore } from '@/stores/conversation'

const POLL_INTERVAL_MS = 2000
const MAX_ATTEMPTS = 15 // ~30s

/** After a Razorpay Checkout success callback, poll GET /api/payment/{id}
 * directly (fast local feedback) until the async webhook resolves it, then
 * hand narration back to the orchestrator so `state` advances correctly. */
export function usePaymentPolling() {
  const isPolling = ref(false)

  async function pollAndNarrate(paymentId: string) {
    const conversation = useConversationStore()
    isPolling.value = true

    for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt++) {
      try {
        const payment = await getPaymentStatus(paymentId)
        if (payment.status === 'executed' || payment.status === 'failed') break
      } catch {
        // transient fetch failure — keep polling until the attempt budget runs out
      }
      await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS))
    }

    isPolling.value = false
    await conversation.sendMessage('Did my payment go through?')
  }

  return { isPolling, pollAndNarrate }
}
