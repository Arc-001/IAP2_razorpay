<script setup lang="ts">
import { useConversationStore } from '@/stores/conversation'
import ChatPanel from './ChatPanel.vue'
import MandateStepper from './MandateStepper.vue'
import AuditTrail from './AuditTrail.vue'

const conversation = useConversationStore()
</script>

<template>
  <div class="flex h-screen flex-col bg-slate-100">
    <header class="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3">
      <h1 class="text-sm font-semibold text-slate-800">AP2 Agentic Commerce — Demo Store</h1>
      <button
        class="text-xs text-slate-400 underline hover:no-underline"
        @click="conversation.startOver()"
      >
        Start Over
      </button>
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
