<script setup lang="ts">
import { ref, watch, onUnmounted } from 'vue'
import { getAuditTrail, ApiError } from '@/lib/api'
import { useConversationStore } from '@/stores/conversation'
import type { AuditLogEntry } from '@/lib/types'

const conversation = useConversationStore()
const entries = ref<AuditLogEntry[]>([])
const loading = ref(false)
const apiBase = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8123'

let pollHandle: ReturnType<typeof setInterval> | null = null

async function refresh() {
  if (!conversation.intentId) return
  loading.value = true
  try {
    const trail = await getAuditTrail(conversation.intentId)
    entries.value = trail.entries
  } catch (err) {
    if (!(err instanceof ApiError && err.status === 404)) throw err
  } finally {
    loading.value = false
  }
}

function stopPolling() {
  if (pollHandle) {
    clearInterval(pollHandle)
    pollHandle = null
  }
}

function startPolling() {
  stopPolling()
  if (conversation.state === 'TERMINAL' || conversation.state === 'PAYMENT_FAILED') return
  pollHandle = setInterval(refresh, 4000)
}

watch(
  () => conversation.intentId,
  (id) => {
    if (id) refresh()
  },
  { immediate: true },
)

watch(
  () => conversation.state,
  () => {
    startPolling()
  },
  { immediate: true },
)

onUnmounted(stopPolling)

function relativeTime(iso: string): string {
  const seconds = Math.round((Date.now() - new Date(iso).getTime()) / 1000)
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.round(seconds / 60)
  return `${minutes}m ago`
}
</script>

<template>
  <div class="rounded-lg border border-slate-200 bg-white p-4">
    <div class="mb-2 flex items-center justify-between">
      <span class="text-xs font-medium uppercase tracking-wide text-slate-400">Audit trail</span>
      <div class="flex items-center gap-2">
        <button
          v-if="conversation.intentId"
          class="text-xs text-slate-400 underline hover:no-underline"
          @click="refresh"
        >
          Refresh
        </button>
        <a
          v-if="conversation.intentId"
          class="text-xs text-slate-400 underline hover:no-underline"
          :href="`${apiBase}/audit/${conversation.intentId}`"
          target="_blank"
          rel="noopener"
        >
          Raw view ↗
        </a>
      </div>
    </div>

    <div v-if="!conversation.intentId" class="text-xs text-slate-400">No transaction yet.</div>
    <ul v-else class="max-h-64 space-y-2 overflow-y-auto text-xs">
      <li
        v-for="entry in [...entries].reverse()"
        :key="entry.id"
        class="rounded border border-slate-100 bg-slate-50 p-2"
      >
        <div class="flex items-center justify-between">
          <span class="rounded bg-slate-200 px-1.5 py-0.5 font-medium text-slate-600">{{ entry.mandate_type }}</span>
          <span class="text-slate-400">{{ relativeTime(entry.created_at) }}</span>
        </div>
        <div class="mt-1 text-slate-600">
          {{ entry.from_state ?? '—' }} → {{ entry.to_state ?? '—' }}
          <span class="text-slate-400">({{ entry.actor }})</span>
        </div>
      </li>
    </ul>
  </div>
</template>
