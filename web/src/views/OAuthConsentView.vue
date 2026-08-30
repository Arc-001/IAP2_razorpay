<script setup lang="ts">
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { approveOAuthAuthorization, ApiError } from '@/lib/api'

const route = useRoute()
const auth = useAuthStore()

const requestId = typeof route.query.request_id === 'string' ? route.query.request_id : ''

const email = ref('')
const password = ref('')

const isApproving = ref(false)
const approveError = ref<string | null>(null)
const denied = ref(false)

async function submitLogin() {
  await auth.login(email.value, password.value)
}

async function allow() {
  isApproving.value = true
  approveError.value = null
  try {
    const { redirect_to } = await approveOAuthAuthorization(requestId)
    // Hands control back to claude.ai's own callback — not a router
    // navigation, a real browser navigation away from this app.
    window.location.href = redirect_to
  } catch (err) {
    approveError.value =
      err instanceof ApiError && err.status === 404
        ? 'This connection request has expired. Go back to Claude and try connecting again.'
        : 'Could not complete the connection. Please try again.'
  } finally {
    isApproving.value = false
  }
}

function deny() {
  // No backend call by design — there's no /deny endpoint (see plan's
  // non-goals). An un-approved request simply expires on its own in the
  // backend's in-memory store; nothing needs to be told about a decline.
  denied.value = true
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

    <div class="w-full max-w-sm space-y-4 rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
      <template v-if="!requestId">
        <h1 class="text-lg font-semibold text-slate-800">Invalid connection link</h1>
        <p class="text-sm text-slate-500">This page needs to be opened from Claude's connector setup.</p>
      </template>

      <template v-else-if="denied">
        <h1 class="text-lg font-semibold text-slate-800">Connection declined</h1>
        <p class="text-sm text-slate-500">Claude was not given access to your account. You can close this window.</p>
      </template>

      <template v-else-if="!auth.isAuthenticated">
        <form class="space-y-4" @submit.prevent="submitLogin">
          <h1 class="text-lg font-semibold text-slate-800">Log in to connect Claude</h1>
          <p class="text-sm text-slate-500">Claude wants to access your AP2 account. Log in to continue.</p>

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
        </form>
      </template>

      <template v-else>
        <h1 class="text-lg font-semibold text-slate-800">Allow Claude to access your AP2 account?</h1>
        <p class="text-sm text-slate-500">
          Signed in as <span class="font-medium text-slate-700">{{ auth.user?.email }}</span
          >. Claude will be able to shop, check out, and view order status on your behalf.
        </p>

        <div v-if="approveError" class="text-sm text-red-600">{{ approveError }}</div>

        <div class="flex gap-2">
          <button
            type="button"
            :disabled="isApproving"
            class="flex-1 rounded-md bg-indigo-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
            @click="allow"
          >
            {{ isApproving ? 'Connecting…' : 'Allow' }}
          </button>
          <button
            type="button"
            :disabled="isApproving"
            class="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-600 disabled:opacity-50"
            @click="deny"
          >
            Deny
          </button>
        </div>
      </template>
    </div>
  </div>
</template>
