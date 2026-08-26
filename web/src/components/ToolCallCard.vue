<script setup lang="ts">
import { computed } from 'vue'
import type {
  ToolCall,
  ProposeIntentOutput,
  CatalogProduct,
  UpsellCandidate,
  CartLineItem,
  ClientPayload,
} from '@/lib/types'
import { formatPaise } from '@/lib/types'
import ProductResultsCard from './ProductResultsCard.vue'
import UpsellCard from './UpsellCard.vue'
import CartSummaryCard from './CartSummaryCard.vue'
import SignatureReveal from './SignatureReveal.vue'
import PaymentStatusCard from './PaymentStatusCard.vue'
import RazorpayCheckoutButton from './RazorpayCheckoutButton.vue'

const props = defineProps<{
  toolCall: ToolCall
}>()

const output = computed(() => props.toolCall.output)
const isError = computed(() => typeof output.value.error === 'string')

const intentStructured = computed(() => (output.value as unknown as ProposeIntentOutput).structured)
const signature = computed(() => (output.value.signature as string | null) ?? null)
const catalogProducts = computed(() => (output.value.products as CatalogProduct[]) ?? [])
const upsellCandidates = computed(() => (output.value.candidates as UpsellCandidate[]) ?? [])
const cartItems = computed(() => (output.value.items as CartLineItem[]) ?? [])
const cartTotal = computed(() => output.value.total_amount as number)
const cartShippingAddress = computed(() => output.value.shipping_address as Record<string, unknown> | null)
const cartStatus = computed(() => output.value.status as string)
const clientPayload = computed(() => output.value.client_payload as ClientPayload)
const paymentId = computed(() => output.value.id as string)
const paymentStatus = computed(() => output.value.status as string)
const razorpayPaymentId = computed(() => (output.value.razorpay_payment_id as string | null) ?? null)
</script>

<template>
  <div v-if="isError" class="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
    {{ output.error }}
  </div>

  <div v-else-if="toolCall.tool === 'propose_intent'" class="rounded-lg border border-slate-200 bg-white p-3 text-sm">
    <div class="mb-1 font-medium text-slate-700">Draft intent</div>
    <dl class="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs text-slate-600">
      <dt class="text-slate-400">Looking for</dt>
      <dd>{{ intentStructured.product_query }}</dd>
      <dt class="text-slate-400">Quantity</dt>
      <dd>{{ intentStructured.quantity }}</dd>
      <template v-if="intentStructured.budget_paise">
        <dt class="text-slate-400">Budget</dt>
        <dd>{{ formatPaise(intentStructured.budget_paise) }}</dd>
      </template>
    </dl>
  </div>

  <SignatureReveal
    v-else-if="toolCall.tool === 'confirm_intent'"
    label="Intent Mandate Signed"
    :signature="signature"
  />

  <ProductResultsCard v-else-if="toolCall.tool === 'search_catalog'" :products="catalogProducts" />

  <UpsellCard
    v-else-if="toolCall.tool === 'suggest_upsell' && upsellCandidates.length > 0"
    :candidates="upsellCandidates"
  />

  <CartSummaryCard
    v-else-if="toolCall.tool === 'propose_cart'"
    :items="cartItems"
    :total-amount="cartTotal"
    :shipping-address="cartShippingAddress"
    :status="cartStatus"
  />

  <SignatureReveal
    v-else-if="toolCall.tool === 'confirm_cart'"
    label="Cart Mandate Confirmed"
    :signature="signature"
  />

  <RazorpayCheckoutButton
    v-else-if="toolCall.tool === 'create_payment' || toolCall.tool === 'retry_payment'"
    :client-payload="clientPayload"
    :payment-id="paymentId"
  />

  <PaymentStatusCard
    v-else-if="toolCall.tool === 'check_payment_status' || toolCall.tool === 'cancel_payment'"
    :status="paymentStatus"
    :razorpay-payment-id="razorpayPaymentId"
  />

  <details v-else class="rounded-lg border border-slate-200 bg-slate-50 p-2 text-xs text-slate-600">
    <summary class="cursor-pointer font-medium">{{ toolCall.tool }}</summary>
    <pre class="mt-1 overflow-x-auto">{{ JSON.stringify({ args: toolCall.args, output: toolCall.output }, null, 2) }}</pre>
  </details>
</template>
