<script setup lang="ts">
import { useConversationStore } from '@/stores/conversation'

const conversation = useConversationStore()

function retry() {
  conversation.sendMessage('Please retry the payment')
}

function cancel() {
  conversation.sendMessage('Cancel the payment')
}
</script>

<template>
  <div class="rounded-lg border border-red-200 bg-red-50 p-3">
    <div class="mb-2 text-sm font-medium text-red-700">Payment failed</div>
    <div class="flex gap-2">
      <button
        class="flex-1 rounded bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700"
        :disabled="conversation.isSending"
        @click="retry"
      >
        Retry Payment
      </button>
      <button
        class="flex-1 rounded border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-100"
        :disabled="conversation.isSending"
        @click="cancel"
      >
        Cancel Order
      </button>
    </div>
  </div>
</template>
