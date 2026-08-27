<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getMyOrders, ApiError } from '@/lib/api'
import { formatPaise } from '@/lib/types'
import { CUSTOMER_NAV_LINKS } from '@/lib/customerNav'
import AppHeader from '@/components/AppHeader.vue'
import type { OrderSummary } from '@/lib/types'

const orders = ref<OrderSummary[]>([])
const isLoading = ref(true)
const error = ref<string | null>(null)

onMounted(async () => {
  try {
    orders.value = await getMyOrders()
  } catch (err) {
    // A 401 already triggers logout + redirect inside lib/api.ts.
    if (!(err instanceof ApiError && err.status === 401)) {
      error.value = 'Could not load your orders.'
    }
  } finally {
    isLoading.value = false
  }
})

function statusColor(order: OrderSummary): string {
  if (order.payment_status === 'executed') return 'text-emerald-600'
  if (order.payment_status === 'failed') return 'text-red-600'
  return 'text-slate-500'
}

function statusLabel(order: OrderSummary): string {
  if (order.payment_status) return `Payment: ${order.payment_status}`
  if (order.cart_status) return `Cart: ${order.cart_status}`
  return `Intent: ${order.intent_status}`
}
</script>

<template>
  <div class="min-h-screen bg-slate-100">
    <AppHeader title="AP2 Agentic Commerce" :links="CUSTOMER_NAV_LINKS" />

    <div class="mx-auto max-w-2xl px-4 py-8">
      <h2 class="mb-4 text-lg font-semibold text-slate-800">Your orders</h2>

      <div v-if="isLoading" class="text-sm text-slate-400">Loading…</div>
      <div v-else-if="error" class="text-sm text-red-600">{{ error }}</div>
      <div v-else-if="orders.length === 0" class="flex flex-col items-center gap-2 rounded-lg border border-dashed border-slate-300 py-12 text-center">
        <span class="flex h-10 w-10 items-center justify-center rounded-full bg-indigo-50 text-lg">📦</span>
        <p class="text-sm text-slate-400">No orders yet.</p>
      </div>

      <ul v-else class="space-y-2">
        <li
          v-for="order in orders"
          :key="order.intent_id"
          class="rounded-lg border border-slate-200 bg-white p-3 text-sm"
        >
          <div class="flex items-center justify-between">
            <span class="font-medium text-slate-800">{{ order.product_query ?? '(unspecified item)' }}</span>
            <span :class="statusColor(order)" class="text-xs font-medium">{{ statusLabel(order) }}</span>
          </div>
          <div class="mt-1 flex items-center justify-between text-xs text-slate-400">
            <span>{{ new Date(order.created_at).toLocaleString() }}</span>
            <span v-if="order.total_amount">{{ formatPaise(order.total_amount) }}</span>
          </div>
        </li>
      </ul>
    </div>
  </div>
</template>
