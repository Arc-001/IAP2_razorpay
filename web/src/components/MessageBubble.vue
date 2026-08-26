<script setup lang="ts">
import type { DisplayEntry } from '@/lib/types'
import ToolCallCard from './ToolCallCard.vue'

defineProps<{
  entry: DisplayEntry
}>()
</script>

<template>
  <div :class="entry.role === 'user' ? 'flex justify-end' : 'flex justify-start'">
    <div class="max-w-[85%] space-y-2">
      <div
        v-if="entry.text"
        class="rounded-2xl px-4 py-2 text-sm"
        :class="[
          entry.role === 'user' ? 'bg-slate-900 text-white' : 'bg-white text-slate-800 border border-slate-200',
          entry.stalled ? 'border-l-4 border-l-amber-400' : '',
        ]"
      >
        {{ entry.text }}
      </div>
      <ToolCallCard
        v-for="(toolCall, i) in entry.toolCalls ?? []"
        :key="i"
        :tool-call="toolCall"
      />
    </div>
  </div>
</template>
