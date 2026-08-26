<script setup lang="ts">
import type { CartLineItem } from '@/lib/types'
import { formatPaise } from '@/lib/types'

defineProps<{
  items: CartLineItem[]
  totalAmount: number
  shippingAddress?: Record<string, unknown> | null
  status: string
}>()
</script>

<template>
  <div class="rounded-lg border border-slate-200 bg-white p-3 text-sm">
    <div class="mb-2 flex items-center justify-between">
      <span class="font-medium text-slate-700">Cart</span>
      <span
        class="rounded-full px-2 py-0.5 text-xs font-medium"
        :class="status === 'confirmed' ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-600'"
      >
        {{ status }}
      </span>
    </div>
    <table class="w-full text-left text-xs">
      <thead>
        <tr class="text-slate-500">
          <th class="pb-1 font-normal">Item</th>
          <th class="pb-1 text-right font-normal">Qty</th>
          <th class="pb-1 text-right font-normal">Total</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in items" :key="item.product_id">
          <td class="py-0.5 text-slate-800">{{ item.name }}</td>
          <td class="py-0.5 text-right text-slate-600">{{ item.quantity }}</td>
          <td class="py-0.5 text-right text-slate-800">{{ formatPaise(item.line_total) }}</td>
        </tr>
      </tbody>
    </table>
    <div class="mt-2 flex items-center justify-between border-t border-slate-200 pt-2">
      <span class="font-medium text-slate-700">Total</span>
      <span class="font-semibold text-slate-900">{{ formatPaise(totalAmount) }}</span>
    </div>
    <div v-if="shippingAddress" class="mt-2 text-xs text-slate-500">
      Shipping to: {{ Object.values(shippingAddress).filter(Boolean).join(', ') }}
    </div>
  </div>
</template>
