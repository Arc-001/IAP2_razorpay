import { ref } from 'vue'
import { getPaymentStatus } from '@/lib/api'
import { useConversationStore } from '@/stores/conversation'

const POLL_INTERVAL_MS = 2000
// Observed real webhook latency through a cloudflared tunnel in testing ran
// right up to ~30-32s — the previous 30s window (15 attempts) occasionally
// gave up just before the webhook actually landed, leaving the customer to
// ask again manually and still get a stale "pending". 45s gives real headroom.
const MAX_ATTEMPTS = 23

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
