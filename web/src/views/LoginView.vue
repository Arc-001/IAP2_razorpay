<script setup lang="ts">
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import router from '@/router'

const auth = useAuthStore()
const route = useRoute()

const email = ref('')
const password = ref('')

async function submit() {
  const ok = await auth.login(email.value, password.value)
  if (ok) {
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    router.push(redirect)
  }
}
</script>

<template>
  <div class="flex min-h-screen flex-col items-center justify-center bg-slate-100 px-4">
    <div class="mb-6 flex items-center gap-2">
      <span class="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-base font-bold text-white">
        A
      </span>
      <span class="text-sm font-semibold text-slate-700">AP2 Agentic Commerce</span>
    </div>

    <form
      class="w-full max-w-sm space-y-4 rounded-lg border border-slate-200 bg-white p-6 shadow-sm"
      @submit.prevent="submit"
    >
      <h1 class="text-lg font-semibold text-slate-800">Log in</h1>

      <div class="space-y-1">
        <label class="text-xs text-slate-500">Email</label>
        <input
          v-model="email"
          type="email"
          required
          autofocus
          class="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
      </div>

      <div class="space-y-1">
        <label class="text-xs text-slate-500">Password</label>
        <input
          v-model="password"
          type="password"
          required
          class="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
      </div>

      <div v-if="auth.error" class="text-sm text-red-600">{{ auth.error }}</div>

      <button
        type="submit"
        :disabled="auth.isSubmitting"
        class="w-full rounded-md bg-indigo-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
      >
        {{ auth.isSubmitting ? 'Logging in…' : 'Log in' }}
      </button>

      <p class="text-center text-xs text-slate-500">
        No account?
        <RouterLink to="/register" class="underline">Register</RouterLink>
      </p>
    </form>
  </div>
</template>
