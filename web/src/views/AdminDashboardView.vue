<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { getAllTransactions, ApiError } from '@/lib/api'
import AppHeader from '@/components/AppHeader.vue'
import type { TransactionAuditOut } from '@/lib/types'

const transactions = ref<TransactionAuditOut[]>([])
const isLoading = ref(true)
const error = ref<string | null>(null)

onMounted(async () => {
  try {
    transactions.value = await getAllTransactions()
  } catch (err) {
    // A 401 already triggers logout + redirect inside lib/api.ts.
    if (!(err instanceof ApiError && err.status === 401)) {
      error.value = 'Could not load transactions.'
    }
  } finally {
    isLoading.value = false
  }
})

function latestPaymentStatus(t: TransactionAuditOut): string | null {
  return t.payment_statuses.length > 0 ? t.payment_statuses[t.payment_statuses.length - 1]! : null
}

function paymentColor(status: string | null): string {
  if (status === 'executed') return 'text-emerald-600'
  if (status === 'failed') return 'text-red-600'
  return 'text-slate-500'
}
</script>

<template>
  <div class="min-h-screen bg-slate-100">
    <AppHeader title="Admin — All transactions" />

    <div class="mx-auto max-w-3xl px-4 py-8">
      <div v-if="isLoading" class="text-sm text-slate-400">Loading…</div>
      <div v-else-if="error" class="text-sm text-red-600">{{ error }}</div>
      <div v-else-if="transactions.length === 0" class="flex flex-col items-center gap-2 rounded-lg border border-dashed border-slate-300 py-12 text-center">
        <span class="flex h-10 w-10 items-center justify-center rounded-full bg-indigo-50 text-lg">📋</span>
        <p class="text-sm text-slate-400">No transactions yet.</p>
      </div>

      <table v-else class="w-full border-collapse overflow-hidden rounded-lg border border-slate-200 bg-white text-sm shadow-sm">
        <thead>
          <tr class="border-b border-slate-200 bg-slate-50 text-left text-xs uppercase text-slate-500">
            <th class="px-3 py-2">Intent</th>
            <th class="px-3 py-2">Intent status</th>
            <th class="px-3 py-2">Signed</th>
            <th class="px-3 py-2">Carts</th>
            <th class="px-3 py-2">Latest payment</th>
            <th class="px-3 py-2">Entries</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="t in transactions"
            :key="t.intent_id"
            class="border-b border-slate-100 transition-colors hover:bg-slate-50"
          >
            <td class="px-3 py-2 font-mono text-xs">
              <RouterLink
                :to="`/admin/transactions/${t.intent_id}`"
                class="text-indigo-600 underline hover:no-underline"
              >
                {{ t.intent_id.slice(0, 8) }}…
              </RouterLink>
            </td>
            <td class="px-3 py-2">{{ t.intent_status }}</td>
            <td class="px-3 py-2">{{ t.intent_signature ? 'yes' : 'no' }}</td>
            <td class="px-3 py-2">{{ t.cart_ids.length }}</td>
            <td class="px-3 py-2 font-medium" :class="paymentColor(latestPaymentStatus(t))">
              {{ latestPaymentStatus(t) ?? '—' }}
            </td>
            <td class="px-3 py-2">{{ t.entries.length }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
