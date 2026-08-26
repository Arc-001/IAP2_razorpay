<script setup lang="ts">
import type { UpsellCandidate } from '@/lib/types'
import { formatPaise } from '@/lib/types'
import { useConversationStore } from '@/stores/conversation'

defineProps<{
  candidates: UpsellCandidate[]
}>()

const conversation = useConversationStore()

function add(name: string) {
  conversation.sendMessage(`Yes, add the ${name}`)
}

function noThanks() {
  conversation.sendMessage('No thanks, skip that')
}
</script>

<template>
  <div class="rounded-lg border border-amber-200 bg-amber-50 p-3">
    <div class="mb-2 text-sm font-medium text-amber-800">You might also like</div>
    <div v-for="candidate in candidates" :key="candidate.id" class="mb-2 last:mb-0">
      <div class="flex items-center justify-between gap-2 text-sm">
        <div>
          <span class="font-medium text-slate-800">{{ candidate.name }}</span>
          <span class="ml-2 text-slate-600">{{ formatPaise(candidate.price) }}</span>
        </div>
        <div class="flex gap-2">
          <button
            class="rounded bg-amber-600 px-2 py-1 text-xs font-medium text-white hover:bg-amber-700"
            @click="add(candidate.name)"
          >
            Add
          </button>
          <button
            class="rounded border border-slate-300 px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100"
            @click="noThanks"
          >
            No thanks
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
