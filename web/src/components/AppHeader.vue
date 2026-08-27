<script setup lang="ts">
import { useRoute, RouterLink } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useConversationStore } from '@/stores/conversation'
import router from '@/router'

const props = defineProps<{
  title: string
  links?: { to: string; label: string; routeName: string }[]
}>()

const route = useRoute()
const auth = useAuthStore()
const conversation = useConversationStore()

function logout() {
  conversation.startOver()
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <header class="flex items-center justify-between border-b border-slate-200 bg-white px-5 py-3">
    <div class="flex items-center gap-3">
      <span
        class="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-indigo-600 text-sm font-bold text-white"
      >
        A
      </span>
      <h1 class="text-sm font-semibold text-slate-800">{{ props.title }}</h1>
    </div>

    <div class="flex items-center gap-4">
      <nav v-if="props.links?.length" class="flex items-center gap-4">
        <RouterLink
          v-for="link in props.links"
          :key="link.to"
          :to="link.to"
          class="text-sm transition-colors"
          :class="
            route.name === link.routeName
              ? 'font-medium text-indigo-600'
              : 'text-slate-500 hover:text-slate-800'
          "
        >
          {{ link.label }}
        </RouterLink>
      </nav>

      <slot name="actions" />

      <div class="flex items-center gap-2 border-l border-slate-200 pl-4">
        <span class="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-500">
          {{ auth.user?.role }}
        </span>
        <span class="hidden text-xs text-slate-400 sm:inline">{{ auth.user?.email }}</span>
        <button class="text-sm text-slate-500 transition-colors hover:text-slate-800" @click="logout">
          Log out
        </button>
      </div>
    </div>
  </header>
</template>
