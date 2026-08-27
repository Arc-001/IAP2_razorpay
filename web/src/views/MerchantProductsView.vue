<script setup lang="ts">
import { ref, onMounted } from 'vue'
import {
  getMerchantProducts,
  createMerchantProduct,
  deleteMerchantProduct,
  ApiError,
} from '@/lib/api'
import { formatPaise } from '@/lib/types'
import { useAuthStore } from '@/stores/auth'
import router from '@/router'
import type { MerchantProduct } from '@/lib/types'

const auth = useAuthStore()

const products = ref<MerchantProduct[]>([])
const isLoading = ref(true)
const error = ref<string | null>(null)
const isCreating = ref(false)

const name = ref('')
const description = ref('')
const category = ref('')
const price = ref<number | null>(null)
const stock = ref<number | null>(null)

function handleError(err: unknown, fallback: string) {
  if (err instanceof ApiError && err.status === 401) {
    auth.logout()
    router.push('/login')
  } else {
    error.value = fallback
  }
}

async function refresh() {
  products.value = await getMerchantProducts()
}

onMounted(async () => {
  try {
    await refresh()
  } catch (err) {
    handleError(err, 'Could not load your products.')
  } finally {
    isLoading.value = false
  }
})

async function addProduct() {
  if (!name.value.trim() || price.value === null) return
  error.value = null
  isCreating.value = true
  try {
    await createMerchantProduct({
      name: name.value,
      description: description.value || null,
      category: category.value || null,
      price: price.value,
      stock: stock.value,
    })
    name.value = ''
    description.value = ''
    category.value = ''
    price.value = null
    stock.value = null
    await refresh()
  } catch (err) {
    handleError(err, 'Could not add that product.')
  } finally {
    isCreating.value = false
  }
}

async function removeProduct(product: MerchantProduct) {
  error.value = null
  try {
    await deleteMerchantProduct(product.id)
    await refresh()
  } catch (err) {
    handleError(err, 'Could not delete that product.')
  }
}

function logout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <div class="min-h-screen bg-slate-100">
    <header class="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3">
      <h1 class="text-sm font-semibold text-slate-800">{{ auth.user?.email }} — Merchant catalog</h1>
      <button class="text-xs text-slate-400 underline hover:no-underline" @click="logout">Log out</button>
    </header>

    <div class="mx-auto max-w-2xl px-4 py-8">
      <div v-if="error" class="mb-4 text-sm text-red-600">{{ error }}</div>

      <section class="mb-6 space-y-3 rounded-lg border border-slate-200 bg-white p-4">
        <h2 class="text-sm font-medium text-slate-700">Add a product</h2>
        <input
          v-model="name"
          type="text"
          placeholder="Name"
          class="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
        <textarea
          v-model="description"
          placeholder="Description"
          rows="2"
          class="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
        <div class="grid grid-cols-3 gap-2">
          <input
            v-model="category"
            type="text"
            placeholder="Category"
            class="rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
          <input
            v-model.number="price"
            type="number"
            placeholder="Price (paise)"
            class="rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
          <input
            v-model.number="stock"
            type="number"
            placeholder="Stock"
            class="rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
        </div>
        <p class="text-xs text-slate-400">
          Tags are generated automatically from the name and description once added.
        </p>
        <button
          :disabled="isCreating"
          class="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
          @click="addProduct"
        >
          {{ isCreating ? 'Adding…' : 'Add product' }}
        </button>
      </section>

      <section class="space-y-2">
        <h2 class="text-sm font-medium text-slate-700">Your products</h2>
        <div v-if="isLoading" class="text-sm text-slate-400">Loading…</div>
        <div v-else-if="products.length === 0" class="text-sm text-slate-400">No products yet.</div>
        <ul v-else class="space-y-2">
          <li
            v-for="p in products"
            :key="p.id"
            class="rounded-lg border border-slate-200 bg-white p-3 text-sm"
          >
            <div class="flex items-center justify-between">
              <span class="font-medium text-slate-800">{{ p.name }}</span>
              <span class="text-xs text-slate-500">{{ formatPaise(p.price) }}</span>
            </div>
            <p v-if="p.description" class="mt-1 text-xs text-slate-500">{{ p.description }}</p>
            <div class="mt-2 flex items-center justify-between">
              <div class="flex flex-wrap gap-1">
                <span
                  v-for="tag in p.tags"
                  :key="tag"
                  class="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600"
                >
                  {{ tag }}
                </span>
              </div>
              <button class="text-xs text-red-500 underline hover:no-underline" @click="removeProduct(p)">
                Remove
              </button>
            </div>
          </li>
        </ul>
      </section>
    </div>
  </div>
</template>
