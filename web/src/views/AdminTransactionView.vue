<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { getAuditTrail, ApiError } from '@/lib/api'
import type { TransactionAuditOut } from '@/lib/types'

const route = useRoute()

const trail = ref<TransactionAuditOut | null>(null)
const isLoading = ref(true)
const error = ref<string | null>(null)

onMounted(async () => {
  try {
    trail.value = await getAuditTrail(route.params.intentId as string)
  } catch (err) {
    // A 401 already triggers logout + redirect inside lib/api.ts.
    if (!(err instanceof ApiError && err.status === 401)) {
      error.value = 'Could not load this transaction.'
    }
  } finally {
    isLoading.value = false
  }
})
</script>

<template>
  <div class="min-h-screen bg-slate-100">
    <header class="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3">
      <h1 class="text-sm font-semibold text-slate-800">Transaction detail</h1>
      <RouterLink to="/admin" class="text-xs text-slate-400 underline hover:no-underline">
        &larr; all transactions
      </RouterLink>
    </header>

    <div class="mx-auto max-w-2xl px-4 py-8">
      <div v-if="isLoading" class="text-sm text-slate-400">Loading…</div>
      <div v-else-if="error" class="text-sm text-red-600">{{ error }}</div>

      <template v-else-if="trail">
        <section class="mb-4 space-y-2 rounded-lg border border-slate-200 bg-white p-4 text-sm">
          <div><span class="text-slate-400">Intent:</span> {{ trail.intent_id }}</div>
          <div><span class="text-slate-400">Status:</span> {{ trail.intent_status }}</div>
          <div class="break-all">
            <span class="text-slate-400">Intent signature:</span>
            {{ trail.intent_signature ?? '(not yet signed)' }}
          </div>
          <div v-for="(sig, i) in trail.cart_signatures" :key="i" class="break-all">
            <span class="text-slate-400">Cart signature {{ i + 1 }}:</span> {{ sig }}
          </div>
          <div v-for="(status, i) in trail.payment_statuses" :key="i">
            <span class="text-slate-400">Payment {{ i + 1 }}:</span> {{ status }}
            (webhook verified: {{ trail.payment_signature_verified[i] }})
          </div>
        </section>

        <section class="rounded-lg border border-slate-200 bg-white p-4">
          <h2 class="mb-2 text-sm font-medium text-slate-700">Audit log</h2>
          <ul class="space-y-2 text-xs">
            <li
              v-for="entry in trail.entries"
              :key="entry.id"
              class="rounded border border-slate-100 bg-slate-50 p-2"
            >
              <div class="flex items-center justify-between">
                <span class="rounded bg-slate-200 px-1.5 py-0.5 font-medium text-slate-600">
                  {{ entry.mandate_type }}
                </span>
                <span class="text-slate-400">{{ new Date(entry.created_at).toLocaleString() }}</span>
              </div>
              <div class="mt-1 text-slate-600">
                {{ entry.from_state ?? '—' }} → {{ entry.to_state ?? '—' }}
                <span class="text-slate-400">({{ entry.actor }})</span>
              </div>
            </li>
          </ul>
        </section>
      </template>
    </div>
  </div>
</template>
