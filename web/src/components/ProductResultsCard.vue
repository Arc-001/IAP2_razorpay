<script setup lang="ts">
import { computed } from 'vue'
import type { CatalogProduct } from '@/lib/types'
import { formatPaise } from '@/lib/types'

const props = defineProps<{
  products: CatalogProduct[]
}>()

const sorted = computed(() => [...props.products].sort((a, b) => a.price - b.price))
</script>

<template>
  <div class="rounded-lg border border-slate-200 bg-white p-3">
    <div class="mb-2 text-sm font-medium text-slate-700">Catalog results</div>
    <div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
      <div
        v-for="product in sorted"
        :key="product.id"
        class="rounded-md border border-slate-200 p-2.5 text-sm"
      >
        <div class="flex items-start justify-between gap-2">
          <span class="font-medium text-slate-800">{{ product.name }}</span>
          <span class="whitespace-nowrap font-semibold text-slate-900">{{ formatPaise(product.price) }}</span>
        </div>
        <div class="mt-1 text-xs text-slate-500">{{ product.merchant_name }}</div>
        <div v-if="product.description" class="mt-1 text-xs text-slate-500">{{ product.description }}</div>
      </div>
    </div>
  </div>
</template>
