<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { getMyConversations, ApiError } from '@/lib/api'
import { useConversationStore } from '@/stores/conversation'
import router from '@/router'
import type { ConversationSummary } from '@/lib/types'

const conversation = useConversationStore()

const conversations = ref<ConversationSummary[]>([])
const isLoading = ref(true)
const error = ref<string | null>(null)

onMounted(async () => {
  try {
    conversations.value = await getMyConversations()
  } catch (err) {
    // A 401 already triggers logout + redirect inside lib/api.ts.
    if (!(err instanceof ApiError && err.status === 401)) {
      error.value = 'Could not load your conversations.'
    }
  } finally {
    isLoading.value = false
  }
})

function startNewChat() {
  conversation.startOver()
  router.push('/')
}
</script>

<template>
  <div class="mx-auto min-h-screen max-w-2xl bg-slate-100 px-4 py-8">
    <div class="mb-4 flex items-center justify-between">
      <h1 class="text-lg font-semibold text-slate-800">Your conversations</h1>
      <div class="flex items-center gap-3">
        <button class="text-sm text-slate-500 underline hover:no-underline" @click="startNewChat">
          New chat
        </button>
        <RouterLink to="/" class="text-sm text-slate-500 underline hover:no-underline">Back to chat</RouterLink>
      </div>
    </div>

    <div v-if="isLoading" class="text-sm text-slate-400">Loading…</div>
    <div v-else-if="error" class="text-sm text-red-600">{{ error }}</div>
    <div v-else-if="conversations.length === 0" class="text-sm text-slate-400">
      No conversations yet — start one from the chat page.
    </div>

    <ul v-else class="space-y-2">
      <li v-for="c in conversations" :key="c.id">
        <RouterLink
          :to="`/history/${c.id}`"
          class="block rounded-lg border border-slate-200 bg-white p-3 hover:border-slate-300"
        >
          <div class="flex items-center justify-between">
            <span class="text-sm font-medium text-slate-800">{{ c.title ?? '(untitled)' }}</span>
            <span class="text-xs text-slate-400">{{ c.state }}</span>
          </div>
          <div class="mt-1 text-xs text-slate-400">
            Updated {{ new Date(c.updated_at).toLocaleString() }}
          </div>
        </RouterLink>
      </li>
    </ul>
  </div>
</template>
