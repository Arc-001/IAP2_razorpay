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

function lineClass(status: string) {
  return status === 'done' ? 'bg-emerald-400' : 'bg-slate-200'
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
    <div class="mb-2 text-xs font-medium uppercase tracking-wide text-slate-400">Mandate Chain</div>
    <ol>
      <li v-for="(stage, i) in stages" :key="stage.index" class="relative" :class="i < stages.length - 1 ? 'pb-4' : ''">
        <span
          v-if="i < stages.length - 1"
          class="absolute left-1.25 top-3 bottom-0 w-px"
          :class="lineClass(stage.status)"
        />
        <div class="relative flex items-center gap-2.5">
          <span class="h-3 w-3 shrink-0 rounded-full border-2" :class="dotClass(stage.status)"></span>
          <span class="text-sm font-medium" :class="labelClass(stage.status)">{{ stage.label }}</span>
        </div>
      </li>
    </ol>

    <RetryCancelBar v-if="conversation.state === 'PAYMENT_FAILED'" class="mt-4" />
  </div>
</template>
