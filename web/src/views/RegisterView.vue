<script setup lang="ts">
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import router from '@/router'

const auth = useAuthStore()

const role = ref<'customer' | 'merchant'>('customer')
const name = ref('')
const merchantName = ref('')
const email = ref('')
const password = ref('')

async function submit() {
  const ok = await auth.register(email.value, password.value, role.value, name.value, merchantName.value)
  if (ok) router.push(role.value === 'merchant' ? '/merchant/products' : '/')
}
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-slate-100 px-4">
    <form class="w-full max-w-sm space-y-4 rounded-lg border border-slate-200 bg-white p-6" @submit.prevent="submit">
      <h1 class="text-lg font-semibold text-slate-800">Create an account</h1>

      <div class="flex gap-2">
        <button
          type="button"
          class="flex-1 rounded-md border px-3 py-1.5 text-sm"
          :class="role === 'customer' ? 'border-slate-900 bg-slate-900 text-white' : 'border-slate-300 text-slate-600'"
          @click="role = 'customer'"
        >
          Customer
        </button>
        <button
          type="button"
          class="flex-1 rounded-md border px-3 py-1.5 text-sm"
          :class="role === 'merchant' ? 'border-slate-900 bg-slate-900 text-white' : 'border-slate-300 text-slate-600'"
          @click="role = 'merchant'"
        >
          Merchant
        </button>
      </div>

      <div class="space-y-1">
        <label class="text-xs text-slate-500">{{ role === 'merchant' ? 'Your name' : 'Name' }}</label>
        <input v-model="name" type="text" required class="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
      </div>

      <div v-if="role === 'merchant'" class="space-y-1">
        <label class="text-xs text-slate-500">Shop name</label>
        <input
          v-model="merchantName"
          type="text"
          required
          class="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
      </div>

      <div class="space-y-1">
        <label class="text-xs text-slate-500">Email</label>
        <input
          v-model="email"
          type="email"
          required
          class="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
      </div>

      <div class="space-y-1">
        <label class="text-xs text-slate-500">Password</label>
        <input
          v-model="password"
          type="password"
          required
          minlength="6"
          class="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
      </div>

      <div v-if="auth.error" class="text-sm text-red-600">{{ auth.error }}</div>

      <button
        type="submit"
        :disabled="auth.isSubmitting"
        class="w-full rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
      >
        {{ auth.isSubmitting ? 'Creating…' : 'Create account' }}
      </button>

      <p class="text-center text-xs text-slate-500">
        Already have an account?
        <RouterLink to="/login" class="underline">Log in</RouterLink>
      </p>
    </form>
  </div>
</template>
