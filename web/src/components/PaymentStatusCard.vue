<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  status: string
  razorpayPaymentId?: string | null
}>()

const badgeClass = computed(() => {
  switch (props.status) {
    case 'executed':
      return 'bg-emerald-100 text-emerald-700'
    case 'failed':
      return 'bg-red-100 text-red-700'
    case 'cancelled':
      return 'bg-slate-200 text-slate-600'
    default:
      return 'bg-amber-100 text-amber-700'
  }
})
</script>

<template>
  <div class="rounded-lg border border-slate-200 bg-white p-3 text-sm">
    <div class="flex items-center justify-between">
      <span class="text-slate-600">Payment status</span>
      <span class="rounded-full px-2 py-0.5 text-xs font-medium capitalize" :class="badgeClass">
        {{ status }}
      </span>
    </div>
    <div v-if="razorpayPaymentId" class="mt-1 font-mono text-xs text-slate-500">
      {{ razorpayPaymentId }}
    </div>
  </div>
</template>
