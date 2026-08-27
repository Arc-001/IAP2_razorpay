<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import {
  getMyProfile,
  updateMyProfile,
  getMyAddresses,
  createAddress,
  updateAddress,
  deleteAddress,
  ApiError,
} from '@/lib/api'
import type { Address, Profile } from '@/lib/types'

const profile = ref<Profile | null>(null)
const addresses = ref<Address[]>([])
const isLoading = ref(true)
const error = ref<string | null>(null)
const savedNotice = ref(false)

const name = ref('')
const contact = ref('')

const newLine1 = ref('')
const newCity = ref('')
const newState = ref('')
const newPostalCode = ref('')

function handleError(err: unknown, fallback: string) {
  // A 401 already triggers logout + redirect inside lib/api.ts.
  if (!(err instanceof ApiError && err.status === 401)) {
    error.value = fallback
  }
}

async function refreshAddresses() {
  addresses.value = await getMyAddresses()
}

onMounted(async () => {
  try {
    profile.value = await getMyProfile()
    name.value = profile.value.name ?? ''
    contact.value = profile.value.contact ?? ''
    await refreshAddresses()
  } catch (err) {
    handleError(err, 'Could not load your profile.')
  } finally {
    isLoading.value = false
  }
})

async function saveProfile() {
  error.value = null
  savedNotice.value = false
  try {
    profile.value = await updateMyProfile({ name: name.value, contact: contact.value })
    savedNotice.value = true
  } catch (err) {
    handleError(err, 'Could not save your profile.')
  }
}

async function addAddress() {
  if (!newLine1.value.trim()) return
  error.value = null
  try {
    await createAddress({ line1: newLine1.value, city: newCity.value, state: newState.value, postal_code: newPostalCode.value })
    newLine1.value = ''
    newCity.value = ''
    newState.value = ''
    newPostalCode.value = ''
    await refreshAddresses()
  } catch (err) {
    handleError(err, 'Could not add that address.')
  }
}

async function makeDefault(address: Address) {
  error.value = null
  try {
    await updateAddress(address.id, { is_default: true })
    await refreshAddresses()
  } catch (err) {
    handleError(err, 'Could not update that address.')
  }
}

async function removeAddress(address: Address) {
  error.value = null
  try {
    await deleteAddress(address.id)
    await refreshAddresses()
  } catch (err) {
    handleError(err, 'Could not delete that address.')
  }
}
</script>

<template>
  <div class="mx-auto min-h-screen max-w-2xl bg-slate-100 px-4 py-8">
    <div class="mb-4 flex items-center justify-between">
      <h1 class="text-lg font-semibold text-slate-800">Your profile</h1>
      <RouterLink to="/" class="text-sm text-slate-500 underline hover:no-underline">Back to chat</RouterLink>
    </div>

    <div v-if="isLoading" class="text-sm text-slate-400">Loading…</div>

    <template v-else>
      <div v-if="error" class="mb-4 text-sm text-red-600">{{ error }}</div>

      <section class="mb-6 space-y-3 rounded-lg border border-slate-200 bg-white p-4">
        <h2 class="text-sm font-medium text-slate-700">Details</h2>
        <div class="space-y-1">
          <label class="text-xs text-slate-500">Name</label>
          <input v-model="name" type="text" class="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
        </div>
        <div class="space-y-1">
          <label class="text-xs text-slate-500">Contact</label>
          <input v-model="contact" type="text" class="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
        </div>
        <div class="flex items-center gap-3">
          <button
            class="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white"
            @click="saveProfile"
          >
            Save
          </button>
          <span v-if="savedNotice" class="text-xs text-emerald-600">Saved.</span>
        </div>
      </section>

      <section class="space-y-3 rounded-lg border border-slate-200 bg-white p-4">
        <h2 class="text-sm font-medium text-slate-700">Saved addresses</h2>

        <ul v-if="addresses.length > 0" class="space-y-2">
          <li
            v-for="a in addresses"
            :key="a.id"
            class="flex items-center justify-between rounded-md border border-slate-200 p-2 text-sm"
          >
            <div>
              <div>{{ a.line1 }}<span v-if="a.city">, {{ a.city }}</span></div>
              <div v-if="a.is_default" class="text-xs text-emerald-600">Default</div>
            </div>
            <div class="flex items-center gap-2">
              <button
                v-if="!a.is_default"
                class="text-xs text-slate-400 underline hover:no-underline"
                @click="makeDefault(a)"
              >
                Make default
              </button>
              <button class="text-xs text-red-500 underline hover:no-underline" @click="removeAddress(a)">
                Remove
              </button>
            </div>
          </li>
        </ul>
        <p v-else class="text-sm text-slate-400">No saved addresses yet.</p>

        <div class="space-y-2 border-t border-slate-100 pt-3">
          <input
            v-model="newLine1"
            type="text"
            placeholder="Address line"
            class="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
          <div class="grid grid-cols-3 gap-2">
            <input
              v-model="newCity"
              type="text"
              placeholder="City"
              class="rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
            <input
              v-model="newState"
              type="text"
              placeholder="State"
              class="rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
            <input
              v-model="newPostalCode"
              type="text"
              placeholder="Postal code"
              class="rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
          <button
            class="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white"
            @click="addAddress"
          >
            Add address
          </button>
        </div>
      </section>
    </template>
  </div>
</template>
