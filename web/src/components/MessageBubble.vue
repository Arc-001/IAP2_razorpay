<script setup lang="ts">
import { computed } from 'vue'
import type { DisplayEntry } from '@/lib/types'
import { renderMarkdown } from '@/lib/markdown'
import ToolCallCard from './ToolCallCard.vue'

const props = defineProps<{
  entry: DisplayEntry
}>()

const html = computed(() => (props.entry.text ? renderMarkdown(props.entry.text) : ''))
</script>

<template>
  <div :class="entry.role === 'user' ? 'flex justify-end' : 'flex justify-start'">
    <div class="max-w-[85%] space-y-2">
      <div
        v-if="entry.text"
        class="markdown-body rounded-2xl px-4 py-2 text-sm"
        :class="[
          entry.role === 'user' ? 'bg-slate-900 text-white' : 'bg-white text-slate-800 border border-slate-200',
          entry.stalled ? 'border-l-4 border-l-amber-400' : '',
        ]"
        v-html="html"
      />
      <ToolCallCard
        v-for="(toolCall, i) in entry.toolCalls ?? []"
        :key="i"
        :tool-call="toolCall"
      />
    </div>
  </div>
</template>

<style scoped>
.markdown-body :deep(p) {
  margin: 0.25em 0;
}
.markdown-body :deep(p:first-child) {
  margin-top: 0;
}
.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}
.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 0.25em 0;
  padding-left: 1.25em;
}
.markdown-body :deep(ul) {
  list-style: disc;
}
.markdown-body :deep(ol) {
  list-style: decimal;
}
.markdown-body :deep(li) {
  margin: 0.15em 0;
}
.markdown-body :deep(strong) {
  font-weight: 600;
}
.markdown-body :deep(a) {
  text-decoration: underline;
  text-underline-offset: 2px;
}
.markdown-body :deep(code) {
  background: rgba(100, 116, 139, 0.15);
  border-radius: 0.25em;
  padding: 0.1em 0.35em;
  font-size: 0.85em;
}
.markdown-body :deep(pre) {
  background: rgba(100, 116, 139, 0.15);
  border-radius: 0.5em;
  padding: 0.5em 0.75em;
  overflow-x: auto;
  margin: 0.4em 0;
}
.markdown-body :deep(pre code) {
  background: none;
  padding: 0;
}
.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  font-weight: 600;
  margin: 0.4em 0 0.2em;
}
.markdown-body :deep(blockquote) {
  border-left: 2px solid rgba(100, 116, 139, 0.4);
  padding-left: 0.6em;
  margin: 0.3em 0;
  opacity: 0.85;
}
</style>
