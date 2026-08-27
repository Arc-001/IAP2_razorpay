<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getMyConversations, ApiError } from '@/lib/api'
import { useConversationStore } from '@/stores/conversation'
import { CUSTOMER_NAV_LINKS } from '@/lib/customerNav'
import AppHeader from '@/components/AppHeader.vue'
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
  <div class="min-h-screen bg-slate-100">
    <AppHeader title="AP2 Agentic Commerce" :links="CUSTOMER_NAV_LINKS">
      <template #actions>
        <button class="text-sm text-slate-500 transition-colors hover:text-slate-800" @click="startNewChat">
          New chat
        </button>
      </template>
    </AppHeader>

    <div class="mx-auto max-w-2xl px-4 py-8">
      <h2 class="mb-4 text-lg font-semibold text-slate-800">Your conversations</h2>

      <div v-if="isLoading" class="text-sm text-slate-400">Loading…</div>
      <div v-else-if="error" class="text-sm text-red-600">{{ error }}</div>
      <div v-else-if="conversations.length === 0" class="flex flex-col items-center gap-2 rounded-lg border border-dashed border-slate-300 py-12 text-center">
        <span class="flex h-10 w-10 items-center justify-center rounded-full bg-indigo-50 text-lg">💬</span>
        <p class="text-sm text-slate-400">No conversations yet — start one from the chat page.</p>
      </div>

      <ul v-else class="space-y-2">
        <li v-for="c in conversations" :key="c.id">
          <RouterLink
            :to="`/history/${c.id}`"
            class="block rounded-lg border border-slate-200 bg-white p-3 transition-colors hover:border-indigo-300"
          >
            <div class="flex items-center justify-between">
              <span class="text-sm font-medium text-slate-800">{{ c.title ?? '(untitled)' }}</span>
              <span class="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-500">{{ c.state }}</span>
            </div>
            <div class="mt-1 text-xs text-slate-400">
              Updated {{ new Date(c.updated_at).toLocaleString() }}
            </div>
          </RouterLink>
        </li>
      </ul>
    </div>
  </div>
</template>
