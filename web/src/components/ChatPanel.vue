<script setup lang="ts">
import { ref, computed, nextTick, watch } from 'vue'
import { useConversationStore } from '@/stores/conversation'
import MessageBubble from './MessageBubble.vue'

const conversation = useConversationStore()
const draft = ref('')
const scrollAnchor = ref<HTMLDivElement | null>(null)

// The two human-confirmation gates (CLAUDE.md §7) are the moments a
// customer most often gets stuck wondering what to type ("so?", "uhmm what
// next?") — give them an unambiguous one-click way to say yes.
const awaitingConfirmation = computed(
  () => conversation.state === 'AWAITING_INTENT_OK' || conversation.state === 'AWAITING_CART_OK',
)

async function send() {
  const text = draft.value.trim()
  if (!text || conversation.isSending) return
  draft.value = ''
  await conversation.sendMessage(text)
}

function confirmQuickAction() {
  conversation.sendMessage('Yes, confirm.')
}

watch(
  () => conversation.displayLog.length,
  async () => {
    await nextTick()
    scrollAnchor.value?.scrollIntoView({ behavior: 'smooth' })
  },
)
</script>

<template>
  <div class="flex h-full flex-col">
    <div class="flex-1 space-y-3 overflow-y-auto p-4">
      <div v-if="conversation.displayLog.length === 0" class="text-sm text-slate-400">
        Tell the assistant what you're looking to buy — e.g. "I want wireless earbuds, budget under 3000 rupees".
      </div>
      <MessageBubble v-for="(entry, i) in conversation.displayLog" :key="i" :entry="entry" />
      <div v-if="conversation.isSending" class="flex justify-start">
        <div class="rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm text-slate-400">
          Thinking…
        </div>
      </div>
      <div v-if="conversation.error" class="rounded-lg border border-red-200 bg-red-50 p-2 text-sm text-red-700">
        {{ conversation.error }}
      </div>
      <div ref="scrollAnchor" />
    </div>

    <div class="border-t border-slate-200">
      <div v-if="awaitingConfirmation" class="bg-slate-50 px-3 pt-2">
        <button
          class="rounded-full bg-emerald-600 px-3 py-1 text-xs font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
          :disabled="conversation.isSending"
          @click="confirmQuickAction"
        >
          ✓ Yes, confirm
        </button>
        <span class="ml-2 text-xs text-slate-400">or type changes below</span>
      </div>

      <form class="flex gap-2 p-3" @submit.prevent="send">
      <input
        v-model="draft"
        type="text"
        placeholder="Type a message…"
        class="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
        :disabled="conversation.isSending"
      />
      <button
        type="submit"
        class="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
        :disabled="conversation.isSending || !draft.trim()"
      >
        Send
      </button>
      </form>
    </div>
  </div>
</template>
