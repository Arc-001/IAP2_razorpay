<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { getMyOrders, ApiError } from '@/lib/api'
import { formatPaise } from '@/lib/types'
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
  <div class="mx-auto min-h-screen max-w-2xl bg-slate-100 px-4 py-8">
    <div class="mb-4 flex items-center justify-between">
      <h1 class="text-lg font-semibold text-slate-800">Your orders</h1>
      <RouterLink to="/" class="text-sm text-slate-500 underline hover:no-underline">Back to chat</RouterLink>
    </div>

    <div v-if="isLoading" class="text-sm text-slate-400">Loading…</div>
    <div v-else-if="error" class="text-sm text-red-600">{{ error }}</div>
    <div v-else-if="orders.length === 0" class="text-sm text-slate-400">No orders yet.</div>

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
</template>
