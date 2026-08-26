<script setup lang="ts">
import { ref } from 'vue'
import type { ClientPayload } from '@/lib/types'
import { openCheckout } from '@/lib/razorpay'
import { usePaymentPolling } from '@/composables/usePaymentPolling'

const props = defineProps<{
  clientPayload: ClientPayload
  paymentId: string
}>()

const { isPolling, pollAndNarrate } = usePaymentPolling()
const dismissed = ref(false)
const opening = ref(false)

async function pay() {
  opening.value = true
  dismissed.value = false
  try {
    await openCheckout(
      props.clientPayload,
      () => {
        pollAndNarrate(props.paymentId)
      },
      () => {
        dismissed.value = true
      },
    )
  } finally {
    opening.value = false
  }
}
</script>

<template>
  <div class="rounded-lg border border-slate-200 bg-white p-3 text-sm">
    <div class="mb-2 flex items-center justify-between">
      <span class="text-slate-600">Amount due</span>
      <span class="font-semibold text-slate-900">
        ₹{{ (clientPayload.amount / 100).toLocaleString('en-IN') }}
      </span>
    </div>

    <div v-if="isPolling" class="flex items-center gap-2 text-slate-600">
      <span class="h-3 w-3 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600"></span>
      <span>Confirming your payment…</span>
    </div>
    <template v-else>
      <button
        class="w-full rounded bg-slate-900 px-3 py-2 font-medium text-white hover:bg-slate-700 disabled:opacity-50"
        :disabled="opening"
        @click="pay"
      >
        Pay Now
      </button>
      <div v-if="dismissed" class="mt-2 text-xs text-slate-500">
        Checkout closed — click Pay Now to try again.
      </div>
    </template>
  </div>
</template>
