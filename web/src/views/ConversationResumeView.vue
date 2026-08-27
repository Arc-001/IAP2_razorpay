<script setup lang="ts">
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useConversationStore } from '@/stores/conversation'
import ChatShell from '@/components/ChatShell.vue'

const route = useRoute()
const conversation = useConversationStore()

onMounted(() => {
  conversation.loadConversation(route.params.conversationId as string)
})
</script>

<template>
  <ChatShell />
</template>
