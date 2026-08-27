<script setup lang="ts">
import { useConversationStore } from '@/stores/conversation'
import { useAuthStore } from '@/stores/auth'
import router from '@/router'
import ChatPanel from './ChatPanel.vue'
import MandateStepper from './MandateStepper.vue'
import AuditTrail from './AuditTrail.vue'

const conversation = useConversationStore()
const auth = useAuthStore()

function startOver() {
  conversation.startOver()
  router.push('/')
}

function logout() {
  conversation.startOver()
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <div class="flex h-screen flex-col bg-slate-100">
    <header class="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3">
      <h1 class="text-sm font-semibold text-slate-800">AP2 Agentic Commerce — Demo Store</h1>
      <div class="flex items-center gap-3">
        <span class="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] uppercase text-slate-500">
          {{ auth.user?.role }}
        </span>
        <span class="text-xs text-slate-400">{{ auth.user?.email }}</span>
        <RouterLink to="/history" class="text-xs text-slate-400 underline hover:no-underline">History</RouterLink>
        <RouterLink to="/profile" class="text-xs text-slate-400 underline hover:no-underline">Profile</RouterLink>
        <RouterLink to="/orders" class="text-xs text-slate-400 underline hover:no-underline">Orders</RouterLink>
        <button class="text-xs text-slate-400 underline hover:no-underline" @click="startOver">Start Over</button>
        <button class="text-xs text-slate-400 underline hover:no-underline" @click="logout">Log out</button>
      </div>
    </header>

    <div class="flex flex-1 gap-4 overflow-hidden p-4">
      <main class="flex-1 overflow-hidden rounded-lg border border-slate-200 bg-white">
        <ChatPanel />
      </main>
      <aside class="hidden w-80 shrink-0 space-y-4 overflow-y-auto lg:block">
        <MandateStepper />
        <AuditTrail />
      </aside>
    </div>
  </div>
</template>
