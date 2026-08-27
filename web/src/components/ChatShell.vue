<script setup lang="ts">
import { useConversationStore } from '@/stores/conversation'
import router from '@/router'
import { CUSTOMER_NAV_LINKS } from '@/lib/customerNav'
import AppHeader from './AppHeader.vue'
import ChatPanel from './ChatPanel.vue'
import MandateStepper from './MandateStepper.vue'
import AuditTrail from './AuditTrail.vue'

const conversation = useConversationStore()

function startOver() {
  conversation.startOver()
  router.push('/')
}
</script>

<template>
  <div class="flex h-screen flex-col bg-slate-100">
    <AppHeader title="AP2 Agentic Commerce" :links="CUSTOMER_NAV_LINKS">
      <template #actions>
        <button
          class="text-sm text-slate-500 transition-colors hover:text-slate-800"
          @click="startOver"
        >
          Start Over
        </button>
      </template>
    </AppHeader>

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
