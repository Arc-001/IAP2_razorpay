<script setup lang="ts">
import { ref, computed } from 'vue'

const props = defineProps<{
  label: string
  signature: string | null
}>()

const expanded = ref(false)
const copied = ref(false)

const truncated = computed(() => {
  const sig = props.signature ?? ''
  if (sig.length <= 28) return sig
  return `${sig.slice(0, 14)}…${sig.slice(-10)}`
})

async function copy() {
  if (!props.signature) return
  await navigator.clipboard.writeText(props.signature)
  copied.value = true
  setTimeout(() => (copied.value = false), 1500)
}
</script>

<template>
  <div class="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm">
    <div class="flex items-center gap-2 font-medium text-emerald-800">
      <span>✓</span>
      <span>{{ label }}</span>
    </div>
    <div v-if="signature" class="mt-2 font-mono text-xs text-emerald-700">
      <span>{{ expanded ? signature : truncated }}</span>
      <div class="mt-1 flex gap-3">
        <button class="underline hover:no-underline" @click="expanded = !expanded">
          {{ expanded ? 'Show less' : 'Show full' }}
        </button>
        <button class="underline hover:no-underline" @click="copy">
          {{ copied ? 'Copied!' : 'Copy' }}
        </button>
      </div>
    </div>
  </div>
</template>
