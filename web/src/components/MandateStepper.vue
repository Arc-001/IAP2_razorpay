<script setup lang="ts">
import { computed } from 'vue'
import { useConversationStore } from '@/stores/conversation'
import { STAGES, stageStatus } from '@/lib/stepper'
import RetryCancelBar from './RetryCancelBar.vue'

const conversation = useConversationStore()

const stages = computed(() =>
  STAGES.map((stage) => ({
    ...stage,
    status: stageStatus(stage.index, conversation.state),
  })),
)

function dotClass(status: string) {
  switch (status) {
    case 'done':
      return 'bg-emerald-500 border-emerald-500'
    case 'active':
      return 'bg-amber-400 border-amber-400 animate-pulse'
    case 'error':
      return 'bg-red-500 border-red-500'
    default:
      return 'bg-white border-slate-300'
  }
}

function labelClass(status: string) {
  switch (status) {
    case 'done':
      return 'text-emerald-700'
    case 'active':
      return 'text-amber-700'
    case 'error':
      return 'text-red-700'
    default:
      return 'text-slate-400'
  }
}
</script>

<template>
  <div class="rounded-lg border border-slate-200 bg-white p-4">
    <div class="mb-1 text-xs font-medium uppercase tracking-wide text-slate-400">Mandate Chain</div>
    <ol class="space-y-3">
      <li v-for="stage in stages" :key="stage.index" class="flex items-center gap-2">
        <span class="h-3 w-3 shrink-0 rounded-full border-2" :class="dotClass(stage.status)"></span>
        <span class="text-sm font-medium" :class="labelClass(stage.status)">{{ stage.label }}</span>
      </li>
    </ol>

    <RetryCancelBar v-if="conversation.state === 'PAYMENT_FAILED'" class="mt-4" />
  </div>
</template>
