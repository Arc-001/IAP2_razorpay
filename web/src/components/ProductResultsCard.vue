<script setup lang="ts">
import { computed } from 'vue'
import type { CatalogProduct } from '@/lib/types'
import { formatPaise } from '@/lib/types'
import { useConversationStore } from '@/stores/conversation'

const props = defineProps<{
  products: CatalogProduct[]
}>()

const sorted = computed(() => [...props.products].sort((a, b) => a.price - b.price))

const conversation = useConversationStore()

function select(product: CatalogProduct) {
  conversation.sendMessage(`Add 1 ${product.name} from ${product.merchant_name} to my order.`)
}
</script>

<template>
  <div class="rounded-lg border border-slate-200 bg-white p-3">
    <div class="mb-2 text-sm font-medium text-slate-700">Catalog results</div>
    <div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
      <div
        v-for="product in sorted"
        :key="product.id"
        class="flex flex-col rounded-md border border-slate-200 p-2.5 text-sm"
      >
        <div class="flex items-start justify-between gap-2">
          <span class="font-medium text-slate-800">{{ product.name }}</span>
          <span class="whitespace-nowrap font-semibold text-slate-900">{{ formatPaise(product.price) }}</span>
        </div>
        <div class="mt-1 text-xs text-slate-500">{{ product.merchant_name }}</div>
        <div v-if="product.description" class="mt-1 text-xs text-slate-500">{{ product.description }}</div>
        <button
          class="mt-2 self-start rounded bg-slate-900 px-2 py-1 text-xs font-medium text-white hover:bg-slate-700"
          :disabled="conversation.isSending"
          @click="select(product)"
        >
          Select
        </button>
      </div>
    </div>
  </div>
</template>
